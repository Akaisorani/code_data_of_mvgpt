import configparser
import os

import oss2


class OSS:
    bucket = None

    @classmethod
    def init(cls):
        config = configparser.ConfigParser()
        config.read('train_mdl/train_oss.ini')
        # config.read('/Users/zhengjianhui/PycharmProjects/mama-ai/train_mdl/train_oss.ini')
        # 获取指定section下的option值
        oss_id = config.get('oss', 'oss_id')
        oss_key = config.get('oss', 'oss_key')
        auth = oss2.Auth(oss_id, oss_key)
        cls.bucket = oss2.Bucket(auth, 'oss-accelerate.XXXcs.com', 'faeet2')

    @classmethod
    def upload(cls, local_path, oss_path):
        if cls.bucket is None: cls.init()
        cls.bucket.put_object_from_file(oss_path, local_path)

    @classmethod
    def download(cls, local_path, oss_path):
        if cls.bucket is None: cls.init()
        cls.bucket.get_object_to_file(oss_path, local_path)

    @classmethod
    def download_dir(cls, local_dir, oss_dir):
        if cls.bucket is None: cls.init()
        if not os.path.exists(local_dir):
            os.mkdir(local_dir)
        for b in oss2.ObjectIterator(cls.bucket, prefix=oss_dir):
            file = os.path.basename(b.key)
            print("filename:", file)
            oss_path = os.path.join(oss_dir, file)
            local_path = os.path.join(local_dir, file)
            print("oss_path", oss_path, "local_path", local_path)
            cls.bucket.get_object_to_file(oss_path, local_path)
        os.system("ls -al {}".format(local_dir))

    @classmethod
    def upload_dir(cls, local_dir, oss_dir):
        if cls.bucket is None: cls.init()
        for file in os.listdir(local_dir):
            print("filename:", file)
            local_path = os.path.join(local_dir, file)
            oss_path = os.path.join(oss_dir, file)
            print("oss_path", oss_path, "local_path", local_path)
            cls.bucket.put_object_from_file(oss_path, local_path)
        cls.ls(oss_dir)

    @classmethod
    def ls(cls, oss_path):
        if cls.bucket is None: cls.init()
        # for b in oss2.ObjectIterator(cls.bucket, prefix=oss_path):
        #     print(b.key, "0B" if b.size == 0 else "{:.2f}MB".format(b.size / (1024 ** 2)))
        model_list = []
        for obj in oss2.ObjectIterator(cls.bucket, prefix=oss_path, delimiter='/'):
            if obj.is_prefix():  # 判断是否是目录
                print("目录：", obj.key.split('/')[-2])
                model_list.append(obj.key.split('/')[-2])
            else:
                print("文件：", obj.key, "0B" if obj.size == 0 else "{:.2f}MB".format(obj.size / (1024 ** 2)))
        return model_list
    @classmethod
    def delete(cls, oss_path):
        if cls.bucket is None: cls.init()
        cls.bucket.delete_object(oss_path)

    @classmethod
    def mkdir(cls, oss_path):
        if cls.bucket is None: cls.init()
        cls.bucket.put_object(oss_path, '')

    @classmethod
    def move(cls, oss_path1, oss_path2):
        if cls.bucket is None: cls.init()
        cls.bucket.copy_object('market-llm-data', oss_path1, oss_path2)
        cls.bucket.delete_object(oss_path1)

    @classmethod
    def copy(cls, oss_path1, oss_path2):
        if cls.bucket is None: cls.init()
        cls.bucket.copy_object('market-llm-data', oss_path1, oss_path2)