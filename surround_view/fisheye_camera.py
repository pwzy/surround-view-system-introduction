import os
import numpy as np
import cv2

from . import param_settings as settings

#  camera = FisheyeCameraModel(camera_file, camera_name)
class FisheyeCameraModel(object):

    """
    Fisheye camera model, for undistorting, projecting and flipping camera frames.
    """
    # camera_param_file = frond.yaml
    # camera_name = "frond"
    def __init__(self, camera_param_file, camera_name):
        if not os.path.isfile(camera_param_file):
            raise ValueError("Cannot find camera param file")

        if camera_name not in settings.camera_names:
            # camera_names = ["front", "back", "left", "right"]
            raise ValueError("Unknown camera name: {}".format(camera_name))

        self.camera_file = camera_param_file
        self.camera_name = camera_name
        self.scale_xy = (1.0, 1.0)
        self.shift_xy = (0, 0)

        self.undistort_maps = None
        self.project_matrix = None

        self.project_shape = settings.project_shapes[self.camera_name]
        #  project_shapes = {
        #      "front": (total_w, yt),
        #      "back":  (total_w, yt),
        #      "left":  (total_h, xl),
        #      "right": (total_h, xl)
        #  }

        self.load_camera_params()

    def load_camera_params(self):
        # <FileStorage object> cv.FileStorage(	filename, flags[, encoding]	)

        # filename is the yaml file to read. 
        fs = cv2.FileStorage(self.camera_file, cv2.FILE_STORAGE_READ) # 将数字或者字符串转为整型。

        # 获得摄像头的内参 
        self.camera_matrix = fs.getNode("camera_matrix").mat() 

        self.dist_coeffs = fs.getNode("dist_coeffs").mat()
        self.resolution = fs.getNode("resolution").mat().flatten()

        scale_xy = fs.getNode("scale_xy").mat()
        if scale_xy is not None:
            self.scale_xy = scale_xy

        shift_xy = fs.getNode("shift_xy").mat()
        if shift_xy is not None:
            self.shift_xy = shift_xy

        # 获得摄像头的投影矩阵,如果不是NONE，则将self.project_matrix设置为project_matrix的值 
        project_matrix = fs.getNode("project_matrix").mat()
        if project_matrix is not None:
            self.project_matrix = project_matrix

        # 释放对象
        fs.release()
        self.update_undistort_maps()
    
    # 更新经过横向和纵向缩放和平移参数设置后的原始图像的参数
    def update_undistort_maps(self):
        new_matrix = self.camera_matrix.copy()
        new_matrix[0, 0] *= self.scale_xy[0]
        new_matrix[1, 1] *= self.scale_xy[1]
        new_matrix[0, 2] += self.shift_xy[0]
        new_matrix[1, 2] += self.shift_xy[1]
        width, height = self.resolution

        # Computes the undistortion and rectification transformation map.
        # 计算无畸变图像和修正转换映射。 https://www.freesion.com/article/3256753294/
        # opencv提供了可以直接使用的矫正算法，即通过calibrate Camera()得到的畸变系数，生成矫正后的图像。
        # 我们可以通过undistort()函数一次性完成；也可以通过initUndistortRectifyMap()和remap()的组合来处理。
        # map1, map2	=	cv.initUndistortRectifyMap(	cameraMatrix, distCoeffs, R, newCameraMatrix, size, m1type[, map1[, map2]]	)
        # self.undistort = (map1, map2)  
        self.undistort_maps = cv2.fisheye.initUndistortRectifyMap(
            self.camera_matrix, # 输入相机内参
            self.dist_coeffs,   # 畸变系数
            np.eye(3),          # 可选的修正变换矩阵
            new_matrix,         # 新的相机矩阵
            (width, height),
            cv2.CV_16SC2        # 第一个输出映射的类型
        )
        return self

    def set_scale_and_shift(self, scale_xy=(1.0, 1.0), shift_xy=(0, 0)):
        self.scale_xy = scale_xy
        self.shift_xy = shift_xy
        # 更新未失真图
        self.update_undistort_maps()
        return self

    def undistort(self, image):
        result = cv2.remap(image, *self.undistort_maps, interpolation=cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_CONSTANT)
        return result

    # proj_image = camera_model.project(und_image)
    # 获得投影图片
    def project(self, image):
        result = cv2.warpPerspective(image, self.project_matrix, self.project_shape)
        # result is the image array
        return result  

    def flip(self, image):
        if self.camera_name == "front":
            return image.copy()

        elif self.camera_name == "back":
            return image.copy()[::-1, ::-1, :]

        elif self.camera_name == "left":
            return cv2.transpose(image)[::-1]

        else:
            return np.flip(cv2.transpose(image), 1)

    def save_data(self):
        fs = cv2.FileStorage(self.camera_file, cv2.FILE_STORAGE_WRITE)
        fs.write("camera_matrix", self.camera_matrix)
        fs.write("dist_coeffs", self.dist_coeffs)
        fs.write("resolution", self.resolution)
        fs.write("project_matrix", self.project_matrix)
        fs.write("scale_xy", np.float32(self.scale_xy))
        fs.write("shift_xy", np.float32(self.shift_xy))
        fs.release()
