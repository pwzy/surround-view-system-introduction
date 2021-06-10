import cv2
from PyQt5.QtCore import qDebug, QMutex

from .base_thread import BaseThread


#  CameraProcessingThread(capture_buffer_manager, camera_id, camera_model)

class CameraProcessingThread(BaseThread):

    """
    Thread for processing individual camera images, i.e. undistort, project and flip.
    """

    def __init__(self,
                 # MultiBufferManager 的实例
                 capture_buffer_manager,
                 device_id,
                 # FisheyeCameraModel 可以计算投影后的图片
                 camera_model,
                 drop_if_full=True,
                 parent=None):
        """
        capture_buffer_manager: an instance of the `MultiBufferManager` object.
        device_id: device number of the camera to be processed.
        camera_model: an instance of the `FisheyeCameraModel` object.
        drop_if_full: drop if the buffer is full.
        """
        super(CameraProcessingThread, self).__init__(parent)
        # 绑定MultiBufferManager的实例
        self.capture_buffer_manager = capture_buffer_manager
        self.device_id = device_id
        # an instance of the `FisheyeCameraModel` object
        self.camera_model = camera_model
        self.drop_if_full = drop_if_full
        self.proc_buffer_manager = None

    def run(self):
        if self.proc_buffer_manager is None:
            raise ValueError("This thread has not been binded to any processing thread yet")

        while True:
            self.stop_mutex.lock()
            if self.stopped:
                self.stopped = False
                self.stop_mutex.unlock()
                break
            self.stop_mutex.unlock()

            self.processing_time = self.clock.elapsed()
            self.clock.start()

            self.processing_mutex.lock()
            raw_frame = self.capture_buffer_manager.get_device(self.device_id).get()
            und_frame = self.camera_model.undistort(raw_frame.image)
            pro_frame = self.camera_model.project(und_frame)
            flip_frame = self.camera_model.flip(pro_frame)
            self.processing_mutex.unlock()

            self.proc_buffer_manager.sync(self.device_id)
            self.proc_buffer_manager.set_frame_for_device(self.device_id, flip_frame)

            # update statistics
            self.update_fps(self.processing_time)
            self.stat_data.frames_processed_count += 1
            # inform GUI of updated statistics
            self.update_statistics_gui.emit(self.stat_data)
