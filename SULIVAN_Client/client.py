#  SULIVAN : Synergistic Understanding and Learning with Interactive robotics,
#            computer Vision, Augmented reality, and Neural networks
#  Copyright 2026 PNU IRLab All rights reserved.
#
#  Made by Jibaek Oh (jibaek8809@pusan.ac.kr), Jihoon Yoon (face5921@pusan.ac.kr),
#          HyeonUk Kang (hwkang0318@pusan.ac.kr)

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

import cv2
import numpy as np
import time
import threading
import json
from collections import deque
import random

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"  # Hide welcome message
import pygame
import logging

import utils.coord_utils as coord
import utils.state as STATE

from .threads.camera_thread import CameraThread
from .threads.mediapipe_thread import MediaPipeThread
from .threads.yolo_thread import YOLOThread
from .threads.video_recorder_thread import VideoRecorderThread
from .threads.tts_thread import TTSThread

from .scenario import Scenario
from .objects.lpips import LPIPSModelLoader

logger = logging.getLogger(__name__)

def assign_players_by_hand_positions(hands, width, height):
    player_zone_map = {}
    mx = width // 2
    my = height // 2
    for hand in hands:
        bbox = hand['bbox']
        cx = bbox[0] + bbox[2] // 2
        cy = bbox[1] + bbox[3] // 2
        dx = cx - mx
        dy = cy - my
        # 아래(플레이어1)
        if (dy >= 0) and (abs(dx) <= abs(dy)):
            player_zone_map[1] = hand
        # 위(플레이어3)
        elif (dy < 0) and (abs(dx) <= abs(dy)):
            player_zone_map[3] = hand
        # 왼쪽(플레이어2)
        elif (dx < 0) and (abs(dx) > abs(dy)):
            player_zone_map[2] = hand
        # 오른쪽(플레이어4)
        elif (dx > 0) and (abs(dx) > abs(dy)):
            player_zone_map[4] = hand
    return player_zone_map

class SULIVAN_Client():
    def __init__(self):
        self.is_exit = False

        pygame.init()

        if config.borderless_pygame_window:
            os.environ['SDL_VIDEO_WINDOW_POS'] = f"-{config.PIXELS_WIDTH},0"
            self.SCREEN = pygame.display.set_mode(
                (config.PIXELS_WIDTH, config.PIXELS_HEIGHT), pygame.NOFRAME)
        else:
            self.SCREEN = pygame.display.set_mode(
                (config.PIXELS_WIDTH, config.PIXELS_HEIGHT))

        pygame.display.set_caption("SULIVAN")
        self.display_images = deque([np.zeros((config.PIXELS_HEIGHT, config.PIXELS_WIDTH, 3), np.uint8)], maxlen=6)
        self._display_lock = threading.Lock()

        self.black_masks = []
        self._black_masks_lock = threading.Lock()

        self.clock = pygame.time.Clock()

        self.default_bg = pygame.image.load("assets/backgrounds/default.png").convert()
        self.default_bg_rect = self.default_bg.get_rect()
        if self.default_bg_rect.width != config.PIXELS_WIDTH or self.default_bg_rect.height != config.PIXELS_HEIGHT:
            self.default_bg = pygame.transform.smoothscale(self.default_bg, (config.PIXELS_WIDTH, config.PIXELS_HEIGHT))
            self.default_bg_rect = self.default_bg.get_rect()
        self.show_default_bg = True

        if config.undistort_camera:
            self.camera_thread = CameraThread(self, config.camera_device, is_rotate=config.use_rotate_camera, use_flip_camera=config.use_flip_camera,
                                               use_camera_projection=config.use_camera_projection,
                                               mtx=config.filename_calibration_matrix, dist=config.filename_distortion_coefficients)
        else:
            self.camera_thread = CameraThread(self, config.camera_device, is_rotate=config.use_rotate_camera, use_flip_camera=config.use_flip_camera,
                                               use_camera_projection=config.use_camera_projection)

        self.mp_thread     = MediaPipeThread(self)
        self.yolo_thread   = YOLOThread(self)
        self.record_thread = None

        self.client_thread = threading.Thread(target=self.loop)
        self._client_stop_event = threading.Event()

        self.tts_thread = TTSThread()
            
        self.scenario = None

        self.camera_thread.start()
        self.camera_thread._ready_event.wait()
        logger.info("Camera thread loaded")

        self.mp_thread.start()
        self.mp_thread._ready_event.wait()
        logger.info("Mediapipe thread loaded")

        self.yolo_thread.start()
        self.yolo_thread._ready_event.wait()
        logger.info("YOLO thread loaded")

        self.tts_thread.start()
        LPIPSModelLoader.get_model()
        logger.info("All threads are ready!")

    def get_players_rps_gesture(self):
        """
        미디어파이프 스레드에서 player별 손 컨트롤 결과를 가위/바위/보로 리턴.
        예: {"player1": "rock", "player2": "scissors", ...}
        """
        hands = self.mp_thread.getHands()
        player_gestures = {}
        player_map = assign_players_by_hand_positions(hands, config.PIXELS_WIDTH, config.PIXELS_HEIGHT)
        for num, hand in player_map.items():
            gesture = self._infer_rps_gesture(hand)
            player_gestures[f"player{num}"] = gesture
        return player_gestures

    def _infer_rps_gesture(self, hand):
        # 손가락 open/close count 기반의 단순 예시. 실제 구현은 미디어파이프 구조에 맞게 조정 필요.
        hand_landmarks = hand.get('landmarks', [])
        finger_count = self._count_open_fingers(hand_landmarks)
        if finger_count == 2:
            return "scissors"
        elif finger_count == 5:
            return "paper"
        else:
            return "rock"
    def _count_open_fingers(self, landmarks):
        # 실제 구현에 맞게 손가락 활성 갯수 판단
        # 임시: return random value for test. (실제는 hand 분석로직 고도화 필요)
        return random.choice([0,2,5])

    def stop(self):
        if self.is_exit:
            return
        self.is_exit = True
        self._client_stop_event.set()
        if self.record_thread is not None:
            self.record_thread.stop()
        self.camera_thread.stop()
        self.mp_thread.stop()
        self.yolo_thread.stop()
        self.stop_tts()
        if self.tts_thread is not None:
            self.tts_thread.stop()
            self.tts_thread.join(timeout=1)
        logger.info("Client stopped")

    def isScenarioLoaded(self):
        return self.scenario is not None

    def loadScenario(self, scenario_name):
        if not self.isScenarioLoaded():
            start_time = time.time()
            if config.record_video:
                self.record_thread = VideoRecorderThread(self, scenario_name, start_time)
                self.record_thread.start()
            logger.info(f"Load scenario: {scenario_name}")
            self.yolo_thread.cleanTrackHistory()
            self.scenario = Scenario(self, scenario_name, start_time)
            self.scenario.start()

    def unloadScenario(self):
        if self.isScenarioLoaded():
            logger.info("Unload scenario")
            pygame.mixer.stop()
            self.stop_tts()
            if config.record_video:
                filename_recorded = self.record_thread.stop()
                self.record_thread.join()
                self.record_thread = None
            else:
                filename_recorded = None
            if config.record_video:
                self.scenario.train_recorder.recordAction("Scenario ended.")
                self.scenario.train_recorder.saveStepRecord()
                train_record = self.scenario.train_recorder.finalizeRecord(filename_recorded)
                try:
                    filename_train_record = os.path.splitext(filename_recorded)[0] + '_train'
                    with open(f"{config.record_dir}/{filename_train_record}.json", 'w', encoding='utf-8') as f:
                        json.dump(train_record, f, indent=4, ensure_ascii=False)
                except Exception as e:
                    logger.error(f"Failed to save train record locally: {e}")
            self.yolo_thread.setMode(STATE.PAUSED)
            self.scenario = None

    def restartScenario(self):
        logger.info("Restarting scenario...")
        if self.isScenarioLoaded():
            scenario_name = self.scenario.name
            logger.info(f"Unloading {scenario_name}...")
            self.unloadScenario()
            logger.info(f"Loading {scenario_name}...")
            self.loadScenario(scenario_name)
        else:
            logger.warning("No scenario to restart")
    
    def getDisplayImage(self):
        with self._display_lock:
            return self.display_images[-1].copy()

    def addBlackMask(self, bbox):
        x, y, w, h = bbox
        rect = pygame.Rect(x, y, w, h)
        with self._black_masks_lock:
            self.black_masks.append(rect)

    def removeBlackMask(self, bbox):
        x, y, w, h = bbox
        rect = pygame.Rect(x, y, w, h)
        with self._black_masks_lock:
            if rect in self.black_masks:
                self.black_masks.remove(rect)

    def play_tts(
        self,
        text: str,
        *,
        rate: str | None = None,
        pitch: str | None = None,
        voice: str | None = None,
        volume: float | None = None,
        wait: bool = False,
    ):
        return
        if self.tts_thread is None:
            logger.warning("TTS thread is not initialized")
            return None
        return self.tts_thread.speak(
            text=text,
            rate=rate,
            pitch=pitch,
            voice=voice,
            volume=volume,
            wait=wait,
        )

    def stop_tts(self) -> None:
        if self.tts_thread is not None:
            self.tts_thread.stop_playback()

    def get_tts_cache_path(self, text: str, *, rate: str | None = None, pitch: str | None = None):
        if self.tts_thread is None:
            return None
        return self.tts_thread.get_cache_path(text, rate=rate, pitch=pitch)

    def run(self):
        self.client_thread.start()
    
    def loop(self):
        while not self._client_stop_event.is_set():
            try:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self._client_stop_event.set()

                if not self.isScenarioLoaded():
                    if self.show_default_bg:
                        self.SCREEN.fill((0,0,0))
                        self.SCREEN.blit(self.default_bg, self.default_bg_rect)
                        self.updateScreen()
                    self.clock.tick(30)
                    continue

                self.SCREEN.fill((0,0,0))

                if self.scenario.getRunningState() != STATE.RUNNING:
                    self.clock.tick(30)
                    continue

                bg = self.scenario.getBackground()
                bg_rect = bg.get_rect()
                bg_rect.x = 0
                bg_rect.y = 0
                self.SCREEN.blit(bg, bg_rect)

                guide_video, guide_video_bbox = self.scenario.getGuideVideo()
                if guide_video is not None:
                    try:
                        if guide_video.frame >= (guide_video.frame_count - 6) or not guide_video.active:
                            guide_video.restart()
                        guide_video.draw(self.SCREEN, guide_video_bbox[0:2])
                    except:
                        pass
                
                # 1. RPS 판정 결과 화면 출력 (winner)
                step_name = self.scenario.getName()
                if step_name == "rps_winner" and self.scenario.rps_result:
                    result = self.scenario.rps_result
                    winner = result['winner']
                    order = result['order']
                    bg = self.scenario.getBackground()
                    self.SCREEN.blit(bg, (0,0))
                    font = pygame.font.SysFont(None, 120)
                    # --- [수정된 부분] ---
                    if winner is None:
                        winner_text = "비겼습니다!"
                    else:
                        winner_text = f"Winner: {winner.capitalize()}"
                    # ------------------
                    winner_img = font.render(winner_text, True, (255,255,0))
                    rect = winner_img.get_rect(center=(config.PIXELS_WIDTH//2, config.PIXELS_HEIGHT//2-100))
                    self.SCREEN.blit(winner_img, rect)
                    font_order = pygame.font.SysFont(None, 90)
                    order_str = "  ".join(str(x) for x in order)
                    order_img = font_order.render(order_str, True, (255,255,255))
                    rect_order = order_img.get_rect(center=(config.PIXELS_WIDTH//2, config.PIXELS_HEIGHT//2+100))
                    self.SCREEN.blit(order_img, rect_order)
                    self.updateScreen()
                    pygame.time.delay(3000)

                # (기타 루프, 오브젝트, 안내 등 기존 코드 동일)
                try:
                    self.scenario.loop()
                    if getattr(self.scenario, 'is_display_runtime', False) is True:
                        self.scenario.drawInformationArea()
                except Exception as e:
                    logger.error(f"An error occurred in scenario loop: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    if getattr(config, 'stop_scenario_on_error', True) is True:
                        self.unloadScenario()

                if config.show_hands_bbox_to_screen:
                    hands = self.mp_thread.getHands()
                    width = config.PIXELS_WIDTH
                    height = config.PIXELS_HEIGHT
                    player_map = assign_players_by_hand_positions(hands, width, height)
                    
                    for pnum, hand in player_map.items():
                        print(f"플레이어{pnum} 감지: hand 좌표={hand['bbox']}")
                    
                    for hand in hands.copy():
                        bbox_color = [255, 0, 0] if hand['type'] == 'Left' else [0, 0, 255]
                        hand_bbox = hand['bbox']
                        hand_rect = pygame.Rect(hand_bbox[0], hand_bbox[1], hand_bbox[2], hand_bbox[3])
                        pygame.draw.rect(self.SCREEN, bbox_color, hand_rect, 6)
                
                with self._black_masks_lock:
                    black_masks_snapshot = self.black_masks.copy()
                for rect in black_masks_snapshot:
                    pygame.draw.rect(self.SCREEN, (0, 0, 0), rect)

                self.updateScreen()
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                import traceback
                logger.error(traceback.format_exc())
                self.clock.tick(30)

        if not self.is_exit:
            self.stop()

    def setShowDefaultBackground(self, show: bool):
        self.show_default_bg = show

    def displayBackground(self, image_path=None, image_cv=None):
        self.SCREEN.fill((0,0,0))
        if image_path is not None:
            bg = pygame.image.load(image_path).convert()
            bg_rect = bg.get_rect()
            self.SCREEN.blit(bg, bg_rect)
        elif image_cv is not None:
            bg = pygame.image.frombuffer(image_cv.tobytes(), image_cv.shape[1::-1], "BGR")
            bg_rect = bg.get_rect()
            self.SCREEN.blit(bg, bg_rect)
        pygame.display.flip()
    
    def updateScreen(self):
        pygame.display.flip()
        screen = pygame.display.get_surface()
        capture = pygame.surfarray.pixels3d(screen)
        frame = cv2.cvtColor(capture.transpose([1, 0, 2]), cv2.COLOR_RGB2BGR)
        del capture
        with self._display_lock:
            self.display_images.append(frame)
        self.clock.tick(30)

if __name__ == '__main__':
    print("Please run main.py!")