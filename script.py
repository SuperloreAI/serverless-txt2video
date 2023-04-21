import json
import requests
import subprocess
from fastapi import FastAPI, Request, Body, Response
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
    "run_id": "1234", # (Optional) a unique identifier for this request
    "params": {
        "prompt": "a beautiful woman",
        "frames": 24
    }
}
"""
async def inference(request: Request):
    global client
    body = await request.body()
    json_body = json.loads(body)
    run_id = uuid.uuid4() if not ("run_id" in json_body) else json_body['run_id']
    model_input = json_body['params']
    
    print('received request', json_body)

    if not ("bucket_output_folder" in json_body):
        print('bucket_output_folder is not in request... exiting...')
        raise ValueError("bucket_output_folder is required")

    if not isinstance(model_input['prompt'], list):
        model_input['prompt'] = [model_input['prompt']]

    res = []
    for i in range(len(model_input['prompt'])):
        print(f'processing prompt {i + 1}/{len(model_input["prompt"])}: {model_input["prompt"][i]}')
        input_value = model_input.copy()
        input_value['prompt'] = model_input['prompt'][i]
    
        response = client.post('/text2video/inference', json = input_value)

        print('response', response.json())
    
        output = response.json()

        if not ('data' in output and 'video_files' in output['data']):
            print('unknown output format')
            return {}

        local_video_file = output['data']['video_files']

        # now we need to write the results to gbucket
        output_video_path = f'{json_body["bucket_output_folder"]}/{run_id}/animation_video_{i}.mp4'
        res.append(output_video_path)
        print('writing video to gbucket', output_video_path)
        write_to_gcp(local_video_file, output_video_path)

    response = Response(content=json.dumps({'data': {'video_files': res}}), status_code=200, media_type="application/json")
    
    return response

def register_endpoints(block, app):
    global client
    app.add_api_route('/healthcheck', healthcheck, methods=['GET'])
    app.add_api_route('/', inference, methods=['POST'])
    client = TestClient(app)

on_app_started(register_endpoints)