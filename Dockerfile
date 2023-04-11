FROM nvidia/cuda:11.7.1-runtime-ubuntu22.04
  
# To use a different model, change the model URL below:
# Real model url https://huggingface.co/damo-vilab/modelscope-damo-text-to-video-synthesis
# ARG MODEL_URL='https://huggingface.co/runwayml/stable-diffusion-v1-5/blob/main/v1-5-pruned-emaonly.ckpt'
# Array representation in a string of controlnet models
# Use a comma to separate the models [IMPORTANT]
ARG MODEL_URLS="\
    https://huggingface.co/damo-vilab/modelscope-damo-text-to-video-synthesis/blob/main/VQGAN_autoencoder.pth,\
    https://huggingface.co/damo-vilab/modelscope-damo-text-to-video-synthesis/blob/main/text2video_pytorch_model.pth,\
    https://huggingface.co/damo-vilab/modelscope-damo-text-to-video-synthesis/blob/main/configuration.json,\
    https://huggingface.co/damo-vilab/modelscope-damo-text-to-video-synthesis/blob/main/open_clip_pytorch_model.bin"


# If you are using a private Huggingface model (sign in required to download) insert your Huggingface
# access token (https://huggingface.co/settings/tokens) below:
ARG HF_TOKEN=''

ARG GCP_SERVICE_ACCOUNT_JSON=''

RUN apt update && apt-get -y install git wget \
    python3.10 python3.10-venv python3-pip \
    build-essential libgl-dev libglib2.0-0 vim \
    ffmpeg
RUN ln -s /usr/bin/python3.10 /usr/bin/python

RUN useradd -ms /bin/bash banana

WORKDIR /app

# used to store temporary files
RUN mkdir -p /app/temp_work_files

# SD Webui
RUN git clone https://github.com/SuperloreAI/stable-diffusion-webui.git && \
    cd stable-diffusion-webui && \
    git checkout 769def1e418c74107e4bfe1c7c990d20faed4c17

WORKDIR /app/stable-diffusion-webui

# # Download the txt2video stuff
# RUN git clone https://github.com/SuperloreAI/sd-webui-text2video.git extensions/sd-webui-text2video && \
#     cd extensions/sd-webui-text2video && \
#     git checkout e38b3e82369f4eaf9bd383ea0a9969a86f981922
    
RUN mkdir -p models/ModelScope/t2v

ENV MODEL_URLS=${MODEL_URLS}
ENV HF_TOKEN=${HF_TOKEN}
ENV GCP_SERVICE_ACCOUNT_JSON=${GCP_SERVICE_ACCOUNT_JSON}

RUN pip install tqdm requests google-cloud-storage
ADD download_models.py .
RUN python download_models.py

ADD prepare.py .
RUN python prepare.py --skip-torch-cuda-test --xformers --reinstall-torch --reinstall-xformers

ADD download.py download.py
RUN python download.py --use-cpu=all

# Download the txt2video stuff
RUN git clone https://github.com/SuperloreAI/sd-webui-text2video.git extensions/sd-webui-text2video && \
    cd extensions/sd-webui-text2video && \
    git checkout e38b3e82369f4eaf9bd383ea0a9969a86f981922

RUN mkdir -p extensions/banana/scripts
ADD script.py extensions/banana/scripts/banana.py
ADD app.py app.py
ADD server.py server.py

CMD ["python", "server.py", "--xformers", "--listen", "--port", "8000"]
