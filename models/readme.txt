因为github很难上传大文件，所以模型文件不提供，请自行下载后放到models文件夹下即可使用。

模型下载方法：

# 1. 进入存放模型的目录（即当前readme.txt文件所在目录）

# 2. 执行克隆 (使用国内镜像)，使用最新版本（目前时间2025-12-6）
git clone https://hf-mirror.com/BAAI/bge-reranker-base

# 3. 保留以下文件即可，删除其他文件以节省空间（平铺在当前目录）
config.json
model.safetensors
tokenizer.json
tokenizer_config.json
special_tokens_map.json
sentencepiece.bpe.model

# 4. 最终目录形式是：
models/bge-reranker-base/{上述6个文件}