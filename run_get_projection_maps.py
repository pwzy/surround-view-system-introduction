"""
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Manually select points to get the projection map
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""
import argparse
import os
import numpy as np
import cv2
from surround_view import FisheyeCameraModel, PointSelector, display_image
import surround_view.param_settings as settings

#  from .fisheye_camera import FisheyeCameraModel
#  from .imagebuffer import MultiBufferManager
#  from .capture_thread import CaptureThread
#  from .process_thread import CameraProcessingThread
#  from .simple_gui import display_image, PointSelector
#  from .birdview import BirdView, ProjectedImageBuffer


#  success = get_projection_map(camera, image)
#  camera_model is the instance of the FisheyeCameraModel.
#  image is the images to be caculate
def get_projection_map(camera_model, image):
    # 获得initUndistortRectifyMap 和 remap 函数处理后的无畸变图
    und_image = camera_model.undistort(image)
    # 此时und_image为矫正后的图，即此时已经生成了矫正后的图像
    name = camera_model.camera_name
    # 
    #  ---------------------------------------------------
    #  | A simple gui point selector.                    |
    #  | Usage:                                          |
    #  |                                                 |
    #  | 1. call the `loop` method to show the image.    |
    #  | 2. click on the image to select key points,     |
    #  |    press `d` to delete the last points.         |
    #  | 3. press `q` to quit, press `Enter` to confirm. |
    #  ---------------------------------------------------
    # a simple gui.
    gui = PointSelector(und_image, title=name)
    # 获取配置中的对应摄像头的参数 project_keypoints
    # dst_points 为每一个标注区域四个点的坐标
    dst_points = settings.project_keypoints[name]
    # 调用loop循环函数显示图像
    # 此时一直为死循环，直到loop结束或者标注失败
    choice = gui.loop()
    # 如果return的值大于0说明标注成功。
    if choice > 0:
        # keypoints为标注的点的个数
        src = np.float32(gui.keypoints)
        # dst 为获得每个区域的四个点的坐标
        dst = np.float32(dst_points)
        # 获得透视变换的矩阵
        camera_model.project_matrix = cv2.getPerspectiveTransform(src, dst)
        proj_image = camera_model.project(und_image)

        ret = display_image("Bird's View", proj_image)
        if ret > 0:
            return True
        if ret < 0:
            cv2.destroyAllWindows()

    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-camera", required=True,
                        choices=["front", "back", "left", "right"],
                        help="The camera view to be projected")
    parser.add_argument("-scale", nargs="+", default=None,
                        help="scale the undistorted image")
    parser.add_argument("-shift", nargs="+", default=None,
                        help="shift the undistorted image")
    args = parser.parse_args()

    # settings for the x-axis and y-xais orientation.
    if args.scale is not None:
        scale = [float(x) for x in args.scale]
    else:
        scale = (1.0, 1.0)

    # The shift of the final image.
    if args.shift is not None:
        shift = [float(x) for x in args.shift]
    else:
        shift = (0, 0)

    # The name of camera.
    camera_name = args.camera
    # The file of camera.
    camera_file = os.path.join(os.getcwd(), "yaml", camera_name + ".yaml")
    image_file = os.path.join(os.getcwd(), "images", camera_name + ".png")
    image = cv2.imread(image_file)

    # The process of the FisheyeCameraModel.
    # 设置参数以及缩放参数
    camera = FisheyeCameraModel(camera_file, camera_name)

    camera.set_scale_and_shift(scale, shift)

    success = get_projection_map(camera, image)
    if success:
        print("saving projection matrix to yaml")
        camera.save_data()
    else:
        print("failed to compute the projection map")


if __name__ == "__main__":
    main()
