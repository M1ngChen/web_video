import subprocess
import os


def extract_frame(video_path, output_image):
    if not os.path.isfile(video_path):
        raise FileNotFoundError("视频文件不存在")
    # 获取视频时长
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', video_path],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    duration = float(result.stdout)
    # 计算中间时间点
    middle_time = "{:.2f}".format(duration / 2)
    command = [
        'ffmpeg',
        '-i', video_path,
        '-ss', middle_time,
        '-vframes', '1',
        output_image
    ]
    subprocess.run(command, check=True)


import cv2

def extract_middle_frame(video_path, output_path):
    # 打开视频文件
    cap = cv2.VideoCapture(video_path)
    
    # 检查视频是否成功打开
    if not cap.isOpened():
        print(f"错误：无法打开视频文件 {video_path}")
        return False
    
    # 获取视频总帧数
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # 计算中间帧的位置
    middle_frame_index = frame_count // 2
    
    # 设置读取位置到中间帧
    cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame_index)
    
    # 读取中间帧
    ret, frame = cap.read()
    
    if ret:
        # 保存中间帧为图像
        cv2.imwrite(output_path, frame)
        print(f"成功提取中间帧并保存至 {output_path}")
        cap.release()
        return True
    else:
        print("错误：无法读取中间帧")
        cap.release()
        return False