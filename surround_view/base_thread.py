from queue import Queue
import cv2
# pyqt的信号槽机制就是可自定义一个信号，可将信号与一个槽函数绑定，每当发送这个信号时，就将调用绑定的槽函数，并将信号包含的参数传递给该槽函数。
# pyqtSignal 就是信号槽

#  pyqtSignal's example
#  # pyqtSignal 信号槽机制就是可自定义一个信号，可将信号与一个槽函数绑定，每次发送这个信号时
#  # 就将调用绑定的槽函数，并将信号包含的参数传递给该槽函数
#  from PyQt5.QtCore import pyqtSignal, QObject
#
#
#  class signal(QObject):
#      # 自定义一个信号
#      # my_sighal is the isinstance of pyqtSignal Class.
#      my_sighal = pyqtSignal(str)
#
#      # 定义一个发送信号的函数
#      def run(self, text):
#          self.my_sighal.emit(text)
#
#
#  class slot(QObject):
#      # 这个函数将用于绑定信号
#      def action(self, text):
#          print("I received that signal:" + text)
#
#
#  if __name__ == '__main__':
#      # 创建类的对象
#      send = signal()
#      receive = slot()
#
#      # 将信号与动作进行绑定
#      send.my_sighal.connect(receive.action)
#      # 发送信号
#      send.run("hello")
#
#      # 将信号与槽函数解绑
#      send.my_sighal.disconnect(receive.action)
#      send.run("hello")


from PyQt5.QtCore import (QThread, QTime, QMutex, pyqtSignal, QMutexLocker)
from .structures import ThreadStatisticsData

# class ThreadStatisticsData(object):
#     def __init__(self):
#         self.average_fps = 0   
#         self.frames_processed_count = 0


# 继承自Qthread类
class BaseThread(QThread):

    """
    所有线程类别的基类。
    Base class for all types of threads (capture, processing, stitching, ...,
    etc). Mainly for collecting statistics of the threads.
    """

    FPS_STAT_QUEUE_LENGTH = 32

    # update_statistics_gui是一个信号量，信号量可以绑定到一个槽
    update_statistics_gui = pyqtSignal(ThreadStatisticsData)

    def __init__(self, parent=None):
        super(BaseThread, self).__init__(parent)
        # some commons 
        self.init_commons()

    def init_commons(self):
        self.stopped = False
        self.stop_mutex = QMutex()
        # QTime用于返回系统的时间
        self.clock = QTime()
        # 定义队列
        self.fps = Queue()
        self.processing_time = 0
        self.processing_mutex = QMutex()
        self.fps_sum = 0
        self.stat_data = ThreadStatisticsData()

    def stop(self):
        with QMutexLocker(self.stop_mutex):
            self.stopped = True

    def update_fps(self, dt):
        # add instantaneous fps value to queue
        if dt > 0:
            self.fps.put(1000 / dt)

        # discard redundant items in the fps queue
        if self.fps.qsize() > self.FPS_STAT_QUEUE_LENGTH:
            self.fps.get()

        # update statistics
        if self.fps.qsize() == self.FPS_STAT_QUEUE_LENGTH:
            while not self.fps.empty():
                self.fps_sum += self.fps.get()

            self.stat_data.average_fps = round(self.fps_sum / self.FPS_STAT_QUEUE_LENGTH, 2)
            self.fps_sum = 0
