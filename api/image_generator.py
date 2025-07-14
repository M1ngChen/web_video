# import threading
# import os
# from api.ffmpeg import extract_middle_frame
# threading.Thread(target=task_queue_run, args=(TASK_QUEUE,TASK_QUEUE_LOCK)).start()


# class PictureLoader:
#     def __init__(self,video_path,images_path):
#         self.video_path = video_path
#         self.images_path = images_path
#         pass
    
#     def run(self):
#         self._extrace_images()
    
#     def _check_images_is_empty(self) -> bool:
#         if os.path.getsize(self.images_path) > 0:
#             return True
#         else:
#             return False
    
#     def _extrace_images(self):
#         if self._check_images_is_empty() is not True:
#             return extract_middle_frame(self.video_path,self.images_path)
#         return True

