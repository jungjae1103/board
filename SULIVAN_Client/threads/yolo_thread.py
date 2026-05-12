#  SULIVAN : Synergistic Understanding and Learning with Interactive robotics,
#            computer Vision, Augmented reality, and Neural networks
#  Copyright 2026 PNU IRLab All rights reserved.
#
#  Made by Jibaek Oh (jibaek8809@pusan.ac.kr), Jihoon Yoon (face5921@pusan.ac.kr),
#          HyeonUk Kang (hwkang0318@pusan.ac.kr)

import cv2
import numpy as np
import threading

from ultralytics import YOLO

from ultralytics.utils.plotting import Annotator, colors

from collections import defaultdict

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from client import SULIVAN_Client

import config
import utils.state as STATE
import utils.coord_utils as coord
import logging

logger = logging.getLogger(__name__)


class YOLOThread(threading.Thread):
    def __init__(self, client: "SULIVAN_Client", get_image_func=None, filter=True):
        self._client = client
        self.get_image_func = get_image_func
        self.filter_yolo = filter
        self.ready = False
        self._ready_event = threading.Event()
        self.mode = STATE.STOPPED

        self._stop_event = threading.Event()
        super().__init__()
        self.name = "YOLO"
        self.daemon = True

        self.scale_factor = 0.5

        self.yolo_threshold = 0.1

        # Choose model
        self.model = YOLO(config.filename_yolo)
        if self.filter_yolo:
            self.model_screen = YOLO(config.filename_yolo)

        self.track_history = defaultdict(lambda: [])

        # Result values
        self.names = self.model.model.names
        self.indexes = {v:k for k,v in self.names.items()} # https://blog.naver.com/wideeyed/222007663089
        
        #print("YOLO classes:", self.names)

        self.yolo_returns = []
        self.yolo_overlay = np.zeros((config.PIXELS_HEIGHT, config.PIXELS_WIDTH, 3), dtype=np.uint8)
        self._data_lock = threading.Lock()


    def stop(self):
        self._stop_event.set()

    def getOverlayImage(self):
        '''Get the image with detection result overlays'''
        with self._data_lock:
            return self.yolo_overlay.copy()

    # Return Bounding boxes
    def getDetection(self):
        '''Get the detection results'''
        with self._data_lock:
            return self.yolo_returns
    
    def getClassName(self, id):
        return self.names[id]
        
    def getClassId(self, name):
        return self.indexes[name]
    
    def setMode(self, mode):
        if mode == STATE.PAUSED or mode == STATE.RUNNING:
            self.mode = mode

    def cleanTrackHistory(self):
        self.track_history = defaultdict(lambda: [])

    def run(self):
        '''Thread main loop'''
        # Matrices for perspective xform and downscale
        downscale_matrix = np.diag([self.scale_factor, self.scale_factor, 1.0])
        M_cp_yolo = downscale_matrix @ config.M_cp # Downscale the image

        while True:
            if self._stop_event.is_set():
                break

            # Get a raw image (for YOLO input)
            if self.get_image_func is not None:
                camera_image = self.get_image_func()
            else:
                camera_image = self._client.camera_thread.getImage()
            if camera_image is None:
                self._stop_event.wait(0.005)
                continue
            
            # Get a mediapipe-annotated image (for annotation)
            overlay_image = np.zeros_like(camera_image, dtype=np.uint8)
            
            if self.mode != STATE.PAUSED:
                # Preprocess camera image
                resized_size = (round(config.PIXELS_WIDTH * self.scale_factor), round(config.PIXELS_HEIGHT * self.scale_factor))
                yolo_process_image = cv2.warpPerspective(camera_image, M_cp_yolo, resized_size)

                # Preprocess screen image
                screen_image = self._client.getDisplayImage()
                screen_image = cv2.resize(screen_image, dsize=resized_size, interpolation=cv2.INTER_LINEAR)

                # Get results from YOLO
                yolo_results = self.model.track(yolo_process_image, persist=True, verbose=False, conf=self.yolo_threshold)
                yolo_boxes = yolo_results[0].boxes.xyxy.cpu()
                
                if self.filter_yolo:
                    yolo_screen_results = self.model_screen.track(screen_image, persist=True, verbose=False, conf=self.yolo_threshold)
                    yolo_screen_boxes = yolo_screen_results[0].boxes.xyxy.cpu().tolist()

                yolo_returns = []

                if self.filter_yolo:
                    if yolo_screen_results[0].boxes.id is not None:
                        # Extract prediction results
                        clss_screen = yolo_screen_results[0].boxes.cls.cpu().tolist()
                    else:
                        clss_screen = []

                # If detection exists
                if yolo_results[0].boxes.id is not None:
                    # Extract prediction results
                    clss = yolo_results[0].boxes.cls.cpu().tolist()           # Type of detection
                    track_ids = yolo_results[0].boxes.id.int().cpu().tolist() # index of tracking
                    confs = yolo_results[0].boxes.conf.float().cpu().tolist() # accuracy
                    # print("class:", clss, " track_ids:", track_ids, " confs:", confs, " boxes:", yolo_boxes)
                    # class: [4.0, 2.0]  track_ids: [6, 7]  confs: [0.8469662666320801, 0.42216867208480835]  boxes: tensor([[396.5140, 139.3747, 442.4747, 188.3130], [358.3623,  99.9655, 380.4308, 129.9171]])

                    # Annotator Init
                    annotator = Annotator(overlay_image, line_width=2)

                    for box, cls, track_id, conf in zip(yolo_boxes, clss, track_ids, confs):
                        # Convert bbox to pygame style (X, Y, W, H)
                        bbox_xyxy = box.tolist() # X1, Y1, X2, Y2

                        # Check with screen bbox
                        bbox_overlapped = False
                        if self.filter_yolo:
                            for cls_screen, bbox_xyxy_screen in zip(clss_screen, yolo_screen_boxes):

                                # If the class is different, skip
                                if cls_screen != cls:
                                    continue

                                # Calculate the intersection area
                                x1 = max(bbox_xyxy[0], bbox_xyxy_screen[0])
                                y1 = max(bbox_xyxy[1], bbox_xyxy_screen[1])
                                x2 = min(bbox_xyxy[2], bbox_xyxy_screen[2])
                                y2 = min(bbox_xyxy[3], bbox_xyxy_screen[3])
                                
                                # if overlapped area exists
                                if x2 > x1 and y2 > y1:
                                    intersection_area = (x2 - x1) * (y2 - y1)
                                    
                                    # Calculate area of bbox_xyxy_screen
                                    screen_area = (bbox_xyxy_screen[2] - bbox_xyxy_screen[0]) * (bbox_xyxy_screen[3] - bbox_xyxy_screen[1])
                                    
                                    # If the intersection area is more than 90% of the screen area, skip the bbox
                                    if intersection_area / screen_area >= 0.9:
                                        bbox_overlapped = True
                                        yolo_screen_boxes.remove(bbox_xyxy_screen)
                                        clss_screen.remove(cls_screen)
                                        break

                        # Scale up the bbox
                        for i in range(len(bbox_xyxy)):
                            bbox_xyxy[i] = round(bbox_xyxy[i] / self.scale_factor)
                        
                        bbox_xywh = bbox_xyxy.copy() # X1, Y1, X2, Y2
                        bbox_xywh[2] = bbox_xywh[2] - bbox_xywh[0] # width
                        bbox_xywh[3] = bbox_xywh[3] - bbox_xywh[1] # height

                        # Change coordinate from Camera to Projector
                        bbox_xywh_camera = coord.fromPixelToCameraBbox(bbox_xywh)
                        bbox_xyxy_camera = bbox_xywh_camera.copy()
                        bbox_xyxy_camera[2] = bbox_xyxy_camera[0] + bbox_xyxy_camera[2] # X2
                        bbox_xyxy_camera[3] = bbox_xyxy_camera[1] + bbox_xyxy_camera[3] # Y2
                        
                        if bbox_overlapped:
                            annotator.box_label(bbox_xyxy_camera, color=colors(int(cls), True), label=f"{self.names[int(cls)]} filtered")
                            continue

                        # Store a detection
                        yolo_returns.append({"class": int(cls), "track_id": track_id, "bbox": bbox_xywh, "score": round(conf, 5)})
                        annotator.box_label(bbox_xyxy_camera, color=colors(int(cls), True), label=f"{self.names[int(cls)]} {round(conf, 3)}")

                        # Store tracking history
                        track = self.track_history[track_id]
                        track.append((int((bbox_xyxy_camera[0] + bbox_xyxy_camera[2]) / 2), int((bbox_xyxy_camera[1] + bbox_xyxy_camera[3]) / 2)))
                        if len(track) > 30:
                            track.pop(0)

                        # Plot tracks
                        points = np.array(track, dtype=np.int32).reshape((-1, 1, 2))
                        cv2.circle(overlay_image, (track[-1]), 7, colors(int(cls), True), -1)
                        cv2.polylines(overlay_image, [points], isClosed=False, color=colors(int(cls), True), thickness=2)
                
                # Save YOLO results
                with self._data_lock:
                    self.yolo_returns = yolo_returns
            else:
                with self._data_lock:
                    self.yolo_returns = []
            
            # Mark as ready
            if self.ready == False:
                self.ready = True
                self._ready_event.set()
                self.mode = STATE.PAUSED

            # Save an overlay image
            with self._data_lock:
                self.yolo_overlay = overlay_image