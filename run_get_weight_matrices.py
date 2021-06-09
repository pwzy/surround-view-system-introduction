import os
import numpy as np
import cv2
from PIL import Image
from surround_view import FisheyeCameraModel, display_image, BirdView
import surround_view.param_settings as settings


def main():
    names = settings.camera_names
    # 读取前后左右的图片
    images = [os.path.join(os.getcwd(), "images", name + ".png") for name in names]
    # 读取已经获得的参数
    yamls = [os.path.join(os.getcwd(), "yaml", name + ".yaml") for name in names]
    # 建立四个FisheyeCameraModel,放到一个列表camera_models中
    camera_models = [FisheyeCameraModel(camera_file, camera_name) for camera_file, camera_name in zip (yamls, names)]

    projected = []
    for image_file, camera in zip(images, camera_models):
        img = cv2.imread(image_file)
        img = camera.undistort(img)
        img = camera.project(img)  # 调用投影函数
        img = camera.flip(img)   # 判断是否需要翻转
        projected.append(img)  # 将所有矫正好的图片放到投影列表里

    birdview = BirdView()
    Gmat, Mmat = birdview.get_weights_and_masks(projected)
    birdview.update_frames(projected)
    birdview.make_luminance_balance().stitch_all_parts()
    birdview.make_white_balance()
    birdview.copy_car_image()
    ret = display_image("BirdView Result", birdview.image)
    if ret > 0:
        Image.fromarray((Gmat * 255).astype(np.uint8)).save("weights.png")
        Image.fromarray(Mmat.astype(np.uint8)).save("masks.png")


if __name__ == "__main__":
    main()
