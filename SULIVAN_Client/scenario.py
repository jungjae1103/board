#  SULIVAN : Synergistic Understanding and Learning with Interactive robotics,
#            computer Vision, Augmented reality, and Neural networks
#  Copyright 2026 PNU IRLab All rights reserved.
#
#  Made by Jibaek Oh (jibaek8809@pusan.ac.kr), Jihoon Yoon (face5921@pusan.ac.kr),
#          HyeonUk Kang (hwkang0318@pusan.ac.kr)

import json
import time
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide" # Hide welcome message
import pygame
from pyvidplayer2 import Video

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from client import SULIVAN_Client

from .train_recorder import TrainRecorder

# Objects
from .objects.object_button import ObjectButton
from .objects.hand_button import HandButton
from .objects.popup import Popup

import config
from .load_step import loadStep
import logging

logger = logging.getLogger(__name__)
import utils.coord_utils as coord
import utils.state as STATE
import utils.path_utils as path
import utils.rps_game as rps_game

class Scenario:
    RPS_PLAYERS = ["player1", "player2", "player3", "player4"]
    RPS_HAND_IMAGE_BY_GESTURE = {
        "scissors": "images/가위.png",
        "rock": "images/바위.png",
        "paper": "images/보.png",
    }

    def __init__(self, client: "SULIVAN_Client", scenario_name, start_time=None):
        self._client = client
        self.name = scenario_name
        self.path_util = path.PathUtil(scenario_name)

        # STATE
        # 0: STOPPED, 1: RUNNING, 2: PAUSE
        self.running_state = STATE.STOPPED

        # Load Scenario config
        if os.path.isfile(f'scenarios/{scenario_name}/config.json'):
            config_filename = f'scenarios/{scenario_name}/config.json'
        else:
            config_filename = 'scenarios/default_config.json' # Use default config

        with open(config_filename, encoding='utf8') as f:
            self.config = json.load(f)

        # Fonts for information area
        self.runtime_font = pygame.font.Font("assets/fonts/NotoSansKR-Medium.ttf",   self.config['info_font_size'])
        self.name_font    = pygame.font.Font("assets/fonts/NotoSansKR-SemiBold.ttf", self.config['name_font_size'])

        # Load steps from scenario file
        self.steps = []
        self.current_step = 0
        with open(f'scenarios/{scenario_name}/scenario.json', encoding='utf8') as f:
            steps_load = json.load(f)

        # Assign step ID
        major_id = -1
        for step in steps_load:
            # nested steps: minor id is assigned
            if isinstance(step, list):
                minor_id = 0
                for substep in step:
                    minor_id += 1
                    substep['id'] = major_id + 0.1 * minor_id
                    self.steps.append(substep)
            elif isinstance(step, dict):
                major_id += 1
                step['id'] = major_id
                self.steps.append(step)

        # define number of steps
        self.total_steps = len(self.steps)

        # Manage events to go to next scenario
        self.completion_events = {}

        # Timer: None(no works), Time object
        if start_time is None:
            self.scenario_start_time = time.time()
        else:
            self.scenario_start_time = start_time
        self.step_start_time = None
        self.last_pause_timestamp = None
        self.step_pause_time = 0
        self.scenario_pause_time = 0
        self.is_display_runtime = False

        # Delay state
        # 0: not started, 1: working(waiting), 2: complete
        self.delay_state = STATE.NOT_STARTED
        self.delay_start_time = None
        self.delay_wait_time = None

        # YOLO track id to recognize place object
        self.yolo_track_id = None

        # Recent work hand: None, "Left", "Right"
        self.recent_hand = None

        # Background count for change to next image
        self.bg = []
        self.bg_count = 0
        self.bg_current_idx = 0
        self.bg_timer = time.time()

        # Objects (Buttons, Detections, Images, Popups, Texts)
        self.buttons = []
        self.detections = []
        self.images = {}
        self.popups = {}
        self.texts = {}
        self.lpips_objects = {}

        # Guide Sound
        self.guide_sound = None
        self.guide_sound_interval = None
        self.guide_sound_last_played_time = time.time()
        
        # Guide Video
        self.guide_video = None
        self.guide_video_bbox = None

        # YOLO (Scenario 기본기반은 유지, 실제 rps logic에선 사용X)
        self.yolo_names   = self._client.yolo_thread.names
        self.yolo_indexes = self._client.yolo_thread.indexes
        if self.config.get('use_yolo', True):
            self._client.yolo_thread.setMode(STATE.RUNNING)
        else:
            self._client.yolo_thread.setMode(STATE.PAUSED)

        # Train Recorder
        self.train_recorder = TrainRecorder(self)

        # ----------- RPS(가위바위보)용 임시 상태 변수 -----------
        self._reset_rps_state()

    def getRunningState(self):
        return self.running_state

    def recordAction(self, action):
        self.train_recorder.recordAction(action)

    def start(self):
        if self.running_state == STATE.STOPPED:
            self.changeStep(0)
            self.running_state = STATE.RUNNING

    def pause(self):
        self.running_state = STATE.PAUSED
        self.last_pause_timestamp = time.time()
        self.recordAction("Scenario paused")

    def resume(self):
        self.running_state = STATE.RUNNING
        pause_time = time.time() - self.last_pause_timestamp
        self.step_pause_time += pause_time
        self.scenario_pause_time += pause_time
        self.recordAction("Scenario resumed")

    def getRunningTimes(self):
        timestamp = time.time()
        scenario_runtime = timestamp - self.scenario_start_time - self.scenario_pause_time
        step_runtime     = timestamp - self.step_start_time - self.step_pause_time
        return scenario_runtime, step_runtime

    def achieveCompletionEvent(self, cond):
        if cond in self.completion_events:
            if not self.completion_events[cond]:
                self.completion_events[cond] = True
                if cond == "delay":
                    pass
                elif cond.startswith("popup:"):
                    cond2 = cond.split(":")[1]
                    logger.info(f"Popup triggered: {cond2}")
                    self.recordAction(f"Popup triggered: {cond2}")
                else:
                    logger.info(f"Condition achieved: {cond}")
                    self.recordAction(f"Condition achieved: {cond}")

    def getCurrentStepInfo(self):
        if self.current_step >= len(self.steps):
            return {"name": "Unknown", "completion_events": []}

        step_data = self.steps[self.current_step]
        completion_events = step_data.get('completion_events', [])
        description = ""
        guide_sound = step_data.get('guide_sound', '')
        if isinstance(guide_sound, str) and guide_sound.startswith('tts:'):
            description = guide_sound[4:].strip()
        # Find objects that trigger completion events
        trigger_objects = []
        for btn_conf in step_data.get('buttons', []):
            if 'completion_event' in btn_conf:
                btn_event = btn_conf['completion_event']
                if btn_event in completion_events or btn_event.startswith('popup:'):
                    trigger_objects.append({
                        "type": "button",
                        "name": btn_conf.get('name', 'Unknown'),
                        "bbox": btn_conf.get('bbox', []),
                        "completion_event": btn_event,
                        "description": f"버튼 '{btn_conf.get('name', '')}' 영역에 손을 {btn_conf.get('timer', 500)}ms 동안 유지"
                    })
        for det_conf in step_data.get('detections', []):
            if 'completion_event' in det_conf:
                det_event = det_conf['completion_event']
                if det_event in completion_events or det_event.startswith('popup:'):
                    trigger_objects.append({
                        "type": "detection",
                        "name": det_conf.get('class', 'Unknown'),
                        "bbox": det_conf.get('bbox', []),
                        "completion_event": det_event,
                        "description": f"'{det_conf.get('class', '')}' 객체를 지정된 영역에 배치"
                    })
        for lpips_conf in step_data.get('lpips', []):
            if 'completion_event' in lpips_conf:
                lpips_event = lpips_conf['completion_event']
                if lpips_event in completion_events or lpips_event.startswith('popup:'):
                    trigger_objects.append({
                        "type": "lpips",
                        "name": lpips_conf.get('name', 'Unknown'),
                        "bbox": lpips_conf.get('bbox', []),
                        "completion_event": lpips_event,
                        "threshold": lpips_conf.get('threshold', 0.1),
                        "description": f"'{lpips_conf.get('name', '')}' 영역이 참조 이미지와 일치하도록 조립"
                    })
        task_descriptions = []
        for obj in trigger_objects:
            task_descriptions.append(f"- {obj['description']}")
        tasks_text = "\n".join(task_descriptions) if task_descriptions else "- 특정 조건 없음"
        scenario_runtime, step_runtime = self.getRunningTimes()
        return {
            "name": step_data.get('name', 'Unknown'),
            "description": description,
            "tasks": tasks_text,
            "completion_events": completion_events,
            "trigger_objects": trigger_objects,
            "scenario_runtime": scenario_runtime,
            "step_runtime": step_runtime,
        }

    def drawInformationArea(self):
        scenario_runtime, step_runtime = self.getRunningTimes()
        scenario_runtime_text = str(int(scenario_runtime / 60)).zfill(2) + ":" + str(int(scenario_runtime % 60)).zfill(2)
        scenario_runtime_render = self.runtime_font.render(scenario_runtime_text, True, (255,255,255))
        scenario_tooltip_render = self.runtime_font.render("총 시간: ", True, (255,255,255))
        step_runtime_text = str(int(step_runtime / 60)).zfill(2) + ":" + str(int(step_runtime % 60)).zfill(2)
        step_runtime_render = self.runtime_font.render(step_runtime_text, True, (255,255,255))
        step_tooltip_render = self.runtime_font.render("현재: ", True, (255,255,255))
        self._client.SCREEN.blit(scenario_tooltip_render, self.config["pose_scenario_tooltip"])
        self._client.SCREEN.blit(step_tooltip_render, self.config["pose_step_tooltip"])
        self._client.SCREEN.blit(scenario_runtime_render, self.config["pose_scenario_runtime"])
        self._client.SCREEN.blit(step_runtime_render, self.config["pose_step_runtime"])

    def loop(self):
        if self.running_state is not STATE.RUNNING:
            return
        step = self.current_step
        step_data = self.steps[step]
        step_name = step_data.get('name', '')
        
        ### ====== 가위바위보 제스처 기반 판정 ======
        if step_name == "rps_start":
            self._reset_rps_state()

        if step_name == "rps_detection":
            player_gestures = self._client.get_players_rps_gesture()  # ex: {"player1": "rock", ...}
            for pkey in self.RPS_PLAYERS:
                if pkey not in self.rps_active_players:
                    ce = f"{pkey}_rps_detected"
                    logger.debug(f"Skipping inactive player {pkey}: auto-completing RPS detection event")
                    self.achieveCompletionEvent(ce)
                    continue
                if pkey in player_gestures and pkey not in self.rps_player_gesture:
                    self.rps_player_gesture[pkey] = player_gestures[pkey]
                    ce = f"{pkey}_rps_detected"
                    self.achieveCompletionEvent(ce)
            self._update_rps_hand_images()
            if len(self.rps_player_gesture) == len(self.rps_active_players) and not self.rps_processed:
                self.rps_result = rps_game.determine_rps_winner(self.rps_player_gesture)
                self.rps_processed = True
        if step_name == "rps_check_result" and self.rps_processed:
            if self.rps_result.get("is_tie", False):
                self.next_rps_step = "rps_tie"
                self.rps_player_gesture = {}
                self.rps_processed = False
            else:
                losers = set(self.rps_result.get("losers", []))
                self.rps_active_players = [
                    player for player in self.rps_active_players if player not in losers
                ]
                if len(self.rps_active_players) <= 1:
                    self.next_rps_step = "rps_winner"
                else:
                    self.next_rps_step = "rps_countdown_3"
                self.rps_player_gesture = {}
                self.rps_processed = False
        if step_name == "rps_tie":
            self.rps_player_gesture = {}
            self.rps_processed = False
            self.next_rps_step = "rps_countdown_3"
        if step_name == "rps_winner":
            pass  # 화면 출력은 client.py 등에서

        # ---------- Delay ----------
        if self.delay_wait_time is not None:
            if self.delay_state == STATE.NOT_STARTED:
                self.delay_state = STATE.WORKING
                self.delay_start_time = time.time()
            elif self.delay_state == STATE.WORKING:
                if time.time() - self.delay_start_time > self.delay_wait_time / 1000:
                    self.delay_state = STATE.COMPLETED
            elif self.delay_state == STATE.COMPLETED:
                self.achieveCompletionEvent("delay")
        else:
            self.delay_state = STATE.COMPLETED

        # ------- Images -------
        for image in self.images.values():
            image.draw(self._client.SCREEN)

        # --------- Texts ---------
        for text in self.texts.values():
            text.draw(self._client.SCREEN)

        # ------- Check any popup is triggered -------
        is_any_popup_triggered = False
        for popup in self.popups.values():
            if popup.getDisplayState() == STATE.WORKING:
                is_any_popup_triggered = True
        
        # Loop objects only if no popup is triggered
        if not is_any_popup_triggered:
            for lpips_obj in self.lpips_objects.values():
                lpips_obj.checkAutoTrigger()
            yolo_result = self._client.yolo_thread.getDetection()
            for detection in self.detections:
                detection.checkPosition(yolo_result)
            for button in self.buttons:
                button.checkHover()
        for popup in self.popups.values():
            popup.checkDisplayTime()

        # --- Go to next step when all conditions are achieved ---
        is_all_conds_completed = True
        for cond, state in self.completion_events.items():
            if not state:
                is_all_conds_completed = False
        if len(self.completion_events) > 0 and is_all_conds_completed:
            self.recordAction("All conditions achieved.")
            if step_name in {"rps_check_result", "rps_tie"} and self.next_rps_step:
                self.changeStep(self.getIndex(self.next_rps_step))
            else:
                self.goToNextStep()
        # Python Hook Loop
        if hasattr(self, '_python_hook') and self._python_hook is not None:
            if hasattr(self._python_hook, 'on_step_loop'):
                self._python_hook.on_step_loop(self._client, self)

    def setRecentHand(self, hand):
        self.recent_hand = hand

    def changeText(self, text_name, new_text):
        text_object = self.texts.get(text_name)
        if text_object is None:
            logger.warning(f"Text '{text_name}' not found in current step.")
            return False
        text_object.setText(new_text)
        return True

    def _update_rps_hand_images(self):
        for player in self.RPS_PLAYERS:
            image_obj = self.images.get(f"rps_hand_{player}")
            if image_obj is None:
                continue

            if player not in self.rps_active_players:
                image_obj.set_visible(False)
                continue

            gesture = self.rps_player_gesture.get(player)
            if gesture is None:
                image_obj.set_visible(False)
                continue

            image_path = self.RPS_HAND_IMAGE_BY_GESTURE.get(gesture)
            if image_path is None:
                image_obj.set_visible(False)
                continue

            try:
                resolved_path = self.path_util.getPath(image_path)
            except FileNotFoundError:
                image_obj.set_visible(False)
                continue

            if image_obj.image_path != image_path:
                image_obj.set_image(image_path)

            image_obj.set_visible(True)

    def _reset_rps_state(self):
        self.rps_active_players = self.RPS_PLAYERS.copy()
        self.rps_player_gesture = {}
        self.rps_processed = False
        self.rps_result = None
        self.next_rps_step = None

    def restart(self, step=None):
        self._client.restartScenario()

    # ============== Move step functions ==============
    def goToNextStep(self, step=None):
        self.changeStep(self.current_step + 1)

    def goToPreviousStep(self, step=None):
        self.changeStep(self.current_step - 1)

    def changeStep(self, step):
        if type(step) is str:
            loadStep(self, self.getIndex(step))
        else:
            loadStep(self, step)

    def getName(self, index=None):
        if index is None:
            index = self.current_step
        return self.steps[index]['name']

    def getIndex(self, name=None):
        if name is None:
            return self.current_step
        for i, step in enumerate(self.steps):
            if step['name'] == name:
                return i
        return None

    def getSteps(self, is_numbered=False):
        steps = []
        for step in self.steps:
            if is_numbered:
                steps.append(f"{step['id']} - {step['name']}")
            else:
                steps.append(step['name'])
        return steps

    def getCurrentStep(self):
        return self.current_step

    def loadGuideSound(self):
        step = self.current_step
        step_data = self.steps[step]
        self.guide_sound_interval = step_data.get('guide_sound_interval')
        if 'guide_sound' not in step_data:
            self.guide_sound = None
            return
        raw_sound = step_data['guide_sound']
        if isinstance(raw_sound, str) and raw_sound.startswith("tts:"):
            tts_text = raw_sound.split("tts:", 1)[1].strip()
            if tts_text:
                self._client.play_tts(tts_text)
            else:
                logger.warning("Guide sound text is empty after tts: prefix")
            self.guide_sound = None
            return
        sound_file = self.path_util.getPath(raw_sound)
        self.guide_sound = pygame.mixer.Sound(sound_file)
        self.guide_sound.set_volume(0.7)
        self.guide_sound.play()
        self.guide_sound_last_played_time = time.time()

    def loadGuideVideo(self):
        step = self.current_step
        step_data = self.steps[step]
        if self.guide_video is not None:
            self.guide_video.stop()
            self.guide_video.close()
        self.guide_video = None
        self.guide_video_bbox = None
        if 'guide_video' in step_data:
            video_path = self.path_util.getPath(step_data['guide_video'])
            video_bbox = coord.fromWorldToPixelBbox(step_data['guide_video_bbox'])
            guide_video = Video(video_path)
            guide_video.resize(video_bbox[2:4])
            self.guide_video = guide_video
            self.guide_video_bbox = video_bbox

    def getGuideVideo(self):
        return self.guide_video, self.guide_video_bbox

    def loadBackground(self):
        step = self.current_step
        bg_names = self.steps[step]['background']
        if not isinstance(bg_names, list):
            bg_names = [bg_names]
        bg_load = []
        for bg_name in bg_names:
            bg_name = self.path_util.getPath(bg_name)
            bg = pygame.image.load(bg_name).convert()
            bg_rect = bg.get_rect()
            if bg_rect.width != config.PIXELS_WIDTH or bg_rect.height != config.PIXELS_HEIGHT:
                bg = pygame.transform.smoothscale(bg, (config.PIXELS_WIDTH, config.PIXELS_HEIGHT))
            bg_load.append(bg)
        self.bg = bg_load.copy()
        return True

    def getBackground(self):
        if (time.time() - self.bg_timer) >= 0.3:
            self.bg_timer = time.time()
            self.bg_current_idx += 1
        if self.bg_current_idx == len(self.bg):
            self.bg_current_idx = 0
        return self.bg[self.bg_current_idx]

if __name__ == '__main__':
    print("Please run main.py!")
