import os
import numpy as np
import cv2
from PIL import Image
from PyQt5.QtCore import QMutex, QWaitCondition, QMutexLocker
from .base_thread import BaseThread
from .imagebuffer import Buffer
from . import param_settings as settings
from .param_settings import xl, xr, yt, yb
from . import utils


class ProjectedImageBuffer(object):

    """
    同步各个摄像头的处理程序
    Class for synchronizing processing threads from different cameras.
    """

    def __init__(self, drop_if_full=True, buffer_size=8):
        self.drop_if_full = drop_if_full
        self.buffer = Buffer(buffer_size)
        self.sync_devices = set()
        self.wc = QWaitCondition()
        self.mutex = QMutex()
        self.arrived = 0
        self.current_frames = dict() # 表示当前每个相机的一张照片

    def bind_thread(self, thread):
        with QMutexLocker(self.mutex):
            self.sync_devices.add(thread.device_id)

        # 建立当前的图片
        name = thread.camera_model.camera_name
        shape = settings.project_shapes[name]
        # shape[::-1]表示维度逆向，然后后面增加一个维度，即通道为3  (100, 500) + (3,) = (100, 500, 3)
        # 表示当前相机的一张图片 以字典来表示
        self.current_frames[thread.device_id] = np.zeros(shape[::-1] + (3,), np.uint8)

        # 绑定到当前这个buffer_manager
        thread.proc_buffer_manager = self

    def get(self):
        return self.buffer.get()

    def set_frame_for_device(self, device_id, frame):
        if device_id not in self.sync_devices:
            raise ValueError("Device not held by the buffer: {}".format(device_id))
        self.current_frames[device_id] = frame

    def sync(self, device_id):
        # only perform sync if enabled for specified device/stream
        self.mutex.lock()
        if device_id in self.sync_devices:
            # increment arrived count
            self.arrived += 1
            # we are the last to arrive: wake all waiting threads
            if self.arrived == len(self.sync_devices):
                self.buffer.add(self.current_frames, self.drop_if_full)
                self.wc.wakeAll()
            # still waiting for other streams to arrive: wait
            else:
                self.wc.wait(self.mutex)
            # decrement arrived count
            self.arrived -= 1
        self.mutex.unlock()

    def wake_all(self):
        with QMutexLocker(self.mutex):
            self.wc.wakeAll()

    def __contains__(self, device_id):
        return device_id in self.sync_devices

    def __str__(self):
        return (self.__class__.__name__ + ":\n" + \
                "devices: {}\n".format(self.sync_devices))


#  # four corners of the rectangular region occupied by the car
#  # top-left (x_left, y_top), bottom-right (x_right, y_bottom)
#  xl = shift_w + 180 + inn_shift_w
#  xr = total_w - xl
#  yt = shift_h + 200 + inn_shift_h
#  yb = total_h - yt
def FI(front_image):
    return front_image[:, :xl]


def FII(front_image):
    return front_image[:, xr:]


def FM(front_image):
    return front_image[:, xl:xr]


def BIII(back_image):
    return back_image[:, :xl]


def BIV(back_image):
    return back_image[:, xr:]


def BM(back_image):
    return back_image[:, xl:xr]


def LI(left_image):
    return left_image[:yt, :]


def LIII(left_image):
    return left_image[yb:, :]


def LM(left_image):
    return left_image[yt:yb, :]


def RII(right_image):
    return right_image[:yt, :]


def RIV(right_image):
    return right_image[yb:, :]


def RM(right_image):
    return right_image[yt:yb, :]


class BirdView(BaseThread):

    #  birdview = BirdView()
    # 所有的参数都采用默认值
    def __init__(self,
                 proc_buffer_manager=None,
                 drop_if_full=True,
                 buffer_size=8,
                 parent=None):
        super(BirdView, self).__init__(parent)
        self.proc_buffer_manager = proc_buffer_manager  # None
        self.drop_if_full = drop_if_full  # True
        # 绑定的buffer
        self.buffer = Buffer(buffer_size)  
        # final image size
        self.image = np.zeros((settings.total_h, settings.total_w, 3), np.uint8)  
        self.weights = None
        self.masks = None
        # car_image = cv2.imread(os.path.join(os.getcwd(), "images", "car.png"))
        # 读入汽车logo的图片
        self.car_image = settings.car_image
        self.frames = None

    def get(self):
        return self.buffer.get()

    def update_frames(self, images):
        #  self.frames 为一个列表，保存的是矫正后的前后左右的视图
        self.frames = images

    # 导入权重图和mask图
    def load_weights_and_masks(self, weights_image, masks_image):
        # 将图片转化为权重值
        GMat = np.asarray(Image.open(weights_image).convert("RGBA"), dtype=np.float) / 255.0
        self.weights = [np.stack((GMat[:, :, k],
                                  GMat[:, :, k],
                                  GMat[:, :, k]), axis=2)
                        for k in range(4)]

        Mmat = np.asarray(Image.open(masks_image).convert("RGBA"), dtype=np.float)
        Mmat = utils.convert_binary_to_bool(Mmat)
        self.masks = [Mmat[:, :, k] for k in range(4)]

    def merge(self, imA, imB, k):
        G = self.weights[k]
        return (imA * G + imB * (1 - G)).astype(np.uint8)

    @property
    def FL(self):
        return self.image[:yt, :xl]

    @property
    def F(self):
        return self.image[:yt, xl:xr]

    @property
    def FR(self):
        return self.image[:yt, xr:]

    @property
    def BL(self):
        return self.image[yb:, :xl]

    @property
    def B(self):
        return self.image[yb:, xl:xr]

    @property
    def BR(self):
        return self.image[yb:, xr:]

    @property
    def L(self):
        return self.image[yt:yb, :xl]

    @property
    def R(self):
        return self.image[yt:yb, xr:]

    @property
    def C(self):
        return self.image[yt:yb, xl:xr]

    def stitch_all_parts(self):
        front, back, left, right = self.frames
        #  def FM(front_image):
        #      return front_image[:, xl:xr]
        # 取车的logo前面的区域
        np.copyto(self.F, FM(front))
        np.copyto(self.B, BM(back))
        np.copyto(self.L, LM(left))
        np.copyto(self.R, RM(right))
        # 生成四个角的图像
        #     def merge(self, imA, imB, k):
                #  G = self.weights[k]
                #  return (imA * G + imB * (1 - G)).astype(np.uint8)
        np.copyto(self.FL, self.merge(FI(front), LI(left), 0))
        np.copyto(self.FR, self.merge(FII(front), RII(right), 1))
        np.copyto(self.BL, self.merge(BIII(back), LIII(left), 2))
        np.copyto(self.BR, self.merge(BIV(back), RIV(right), 3))

    def copy_car_image(self):
        np.copyto(self.C, self.car_image)

    def make_luminance_balance(self):

        def tune(x):
            if x >= 1:
                return x * np.exp((1 - x) * 0.5)
            else:
                return x * np.exp((1 - x) * 0.8)

        # 分别为前后左右的四张图片
        front, back, left, right = self.frames
        # 分别为四角的mask
        m1, m2, m3, m4 = self.masks
        # 每张图片分出三个通道
        Fb, Fg, Fr = cv2.split(front)
        Bb, Bg, Br = cv2.split(back)
        Lb, Lg, Lr = cv2.split(left)
        Rb, Rg, Rr = cv2.split(right)

        a1 = utils.mean_luminance_ratio(RII(Rb), FII(Fb), m2)
        a2 = utils.mean_luminance_ratio(RII(Rg), FII(Fg), m2)
        a3 = utils.mean_luminance_ratio(RII(Rr), FII(Fr), m2)

        b1 = utils.mean_luminance_ratio(BIV(Bb), RIV(Rb), m4)
        b2 = utils.mean_luminance_ratio(BIV(Bg), RIV(Rg), m4)
        b3 = utils.mean_luminance_ratio(BIV(Br), RIV(Rr), m4)

        c1 = utils.mean_luminance_ratio(LIII(Lb), BIII(Bb), m3)
        c2 = utils.mean_luminance_ratio(LIII(Lg), BIII(Bg), m3)
        c3 = utils.mean_luminance_ratio(LIII(Lr), BIII(Br), m3)

        d1 = utils.mean_luminance_ratio(FI(Fb), LI(Lb), m1)
        d2 = utils.mean_luminance_ratio(FI(Fg), LI(Lg), m1)
        d3 = utils.mean_luminance_ratio(FI(Fr), LI(Lr), m1)

        t1 = (a1 * b1 * c1 * d1)**0.25
        t2 = (a2 * b2 * c2 * d2)**0.25
        t3 = (a3 * b3 * c3 * d3)**0.25
    
        #######################################################################
        x1 = t1 / (d1 / a1)**0.5
        x2 = t2 / (d2 / a2)**0.5
        x3 = t3 / (d3 / a3)**0.5

        x1 = tune(x1)
        x2 = tune(x2)
        x3 = tune(x3)

        Fb = utils.adjust_luminance(Fb, x1)
        Fg = utils.adjust_luminance(Fg, x2)
        Fr = utils.adjust_luminance(Fr, x3)

        #######################################################################
        y1 = t1 / (b1 / c1)**0.5
        y2 = t2 / (b2 / c2)**0.5
        y3 = t3 / (b3 / c3)**0.5

        y1 = tune(y1)
        y2 = tune(y2)
        y3 = tune(y3)

        Bb = utils.adjust_luminance(Bb, y1)
        Bg = utils.adjust_luminance(Bg, y2)
        Br = utils.adjust_luminance(Br, y3)

        #######################################################################
        z1 = t1 / (c1 / d1)**0.5
        z2 = t2 / (c2 / d2)**0.5
        z3 = t3 / (c3 / d3)**0.5

        z1 = tune(z1)
        z2 = tune(z2)
        z3 = tune(z3)

        Lb = utils.adjust_luminance(Lb, z1)
        Lg = utils.adjust_luminance(Lg, z2)
        Lr = utils.adjust_luminance(Lr, z3)

        #######################################################################
        w1 = t1 / (a1 / b1)**0.5
        w2 = t2 / (a2 / b2)**0.5
        w3 = t3 / (a3 / b3)**0.5

        w1 = tune(w1)
        w2 = tune(w2)
        w3 = tune(w3)

        Rb = utils.adjust_luminance(Rb, w1)
        Rg = utils.adjust_luminance(Rg, w2)
        Rr = utils.adjust_luminance(Rr, w3)

        #######################################################################
        self.frames = [cv2.merge((Fb, Fg, Fr)),
                       cv2.merge((Bb, Bg, Br)),
                       cv2.merge((Lb, Lg, Lr)),
                       cv2.merge((Rb, Rg, Rr))]
        return self

    # images为矫正后的前后左右的图片
    #  # four corners of the rectangular region occupied by the car
    #  # top-left (x_left, y_top), bottom-right (x_right, y_bottom)
    #  xl = shift_w + 180 + inn_shift_w
    #  xr = total_w - xl
    #  yt = shift_h + 200 + inn_shift_h
    #  yb = total_h - yt

    #  def FI(front_image):
    #      return front_image[:, :xl]

    #  def LI(left_image):
    #      return left_image[:yt, :]
    # xl 为车的logo的四边的位置
    def get_weights_and_masks(self, images):
        front, back, left, right = images
        # FI 函数为获取前面图像左边的部分，LI为获得左边图像的右边的部分
        # G0 为权重值，M0为mask
        G0, M0 = utils.get_weight_mask_matrix(FI(front), LI(left))
        G1, M1 = utils.get_weight_mask_matrix(FII(front), RII(right))
        G2, M2 = utils.get_weight_mask_matrix(BIII(back), LIII(left))
        G3, M3 = utils.get_weight_mask_matrix(BIV(back), RIV(right))
        # 进行三通道的拼接，最后一个纬度为通道，即H，W，C
        self.weights = [np.stack((G, G, G), axis=2) for G in (G0, G1, G2, G3)]
        self.masks = [(M / 255.0).astype(np.int) for M in (M0, M1, M2, M3)]
        return np.stack((G0, G1, G2, G3), axis=2), np.stack((M0, M1, M2, M3), axis=2)

    def make_white_balance(self):
        self.image = utils.make_white_balance(self.image)

    def run(self):
        if self.proc_buffer_manager is None:
            raise ValueError("This thread requires a buffer of projected images to run")

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

            # 从proc_buffer_manager中获取当当前的图片，然后进行拼接
            self.update_frames(self.proc_buffer_manager.get().values())
            self.make_luminance_balance().stitch_all_parts()
            self.make_white_balance()
            self.copy_car_image()
            self.buffer.add(self.image.copy(), self.drop_if_full)
            self.processing_mutex.unlock()

            # update statistics
            self.update_fps(self.processing_time)
            self.stat_data.frames_processed_count += 1
            # inform GUI of updated statistics
            self.update_statistics_gui.emit(self.stat_data)
