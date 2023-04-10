import json
import requests
import subprocess
from fastapi import FastAPI, Request, Body
from fastapi.testclient import TestClient
from modules.script_callbacks import on_app_started
import os 
from google.cloud import storage
import uuid


client = None

# Parse the JSON data
secret_json_data = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
secret_data = json.loads(secret_json_data.replace('\n', '\\n'))
# gcp_client = storage.Client.from_service_account_json(secret_file)
gcp_client = storage.Client.from_service_account_info(secret_data)
output_bucket = "superlore-txt2video-383827"

def healthcheck():
    gpu = False
    out = subprocess.run("nvidia-smi", shell=True)
    if out.returncode == 0: # success state on shell command
        gpu = True
    return {"state": "healthy", "gpu": gpu}

def write_to_gcp(local_filepath, output_filepath, bucket_name=output_bucket):
    # Get a bucket object
    bucket = gcp_client.get_bucket(bucket_name)

    # Create a blob object for the file
    blob = bucket.blob(output_filepath)

    # Upload the file to the bucket
    blob.upload_from_filename(local_filepath)

"""
API request body:
{
    "bucket_output_folder": "newton", # (Optional) where you will find your output files 
    "params": {
        "prompt": "a beautiful woman",
        frames: 24
    }
}
"""
async def inference(request: Request):
    global client
    body = await request.body()
    model_input = json.loads(body)
    run_id = uuid.uuid4()
    
    print('received request', model_input)

    if not ("bucket_output_folder" in model_input):
        print('bucket_output_folder is not in request... exiting...')
        raise ValueError("bucket_output_folder is required")

    if not isinstance(model_input['prompt'], list):
        model_input['prompt'] = [model_input['prompt']]

    for i in range(len(model_input['prompt'])):
        print(f'processing prompt {i}/{len(model_input["prompt"])}: {model_input["prompt"][i]}')
        input_value = model_input.copy()
        input_value['prompt'] = model_input['prompt'][i]
    
        response = client.post('/text2video/inference', json = model_input)

        print('response', response.json())
    
        output = response.json()

        if not ('data' in output and 'video_files' in output['data']):
            print('unknown ouptut format')
            return {}

        local_video_file = output['data']['video_files'][0]

        # now we need to write the results to gbucket
        output_video_path = f'{model_input["output_bucket_path"]}/{run_id}/animation_video_{i}.mp4'
        print('writing video to gbucket', local_video_file)
        write_to_gcp(local_video_file, output_video_path)

    return output

def register_endpoints(block, app):
    global client
    app.add_api_route('/healthcheck', healthcheck, methods=['GET'])
    app.add_api_route('/', inference, methods=['POST'])
    client = TestClient(app)

on_app_started(register_endpoints)