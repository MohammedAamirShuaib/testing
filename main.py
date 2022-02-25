from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
import base64
import docx
import shutil
import sys
import time
import requests
from transcribe import *
from assemblyai_data_extraction import json_data_extraction
from typing import List
import uuid
from html_content import *
import boto3

app = FastAPI()

# Global variables

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
s3 = boto3.client('s3')

def startup():
  global dir_name, log_list
  dir_name = str(uuid.uuid4())
  log_list = []


@app.get('/', response_class=HTMLResponse)
async def file_temp(request: Request):
  startup()
  return templates.TemplateResponse("webpage.html", {'request': request})


@app.post("/", response_class=HTMLResponse)
async def create_upload_files(*,files: List[UploadFile] = File(...), request: Request):

  for file in files:
    if file.filename == "":
      wc = "No Files Uploaded"
      log_list.append("No files were uploaded")
      return HTMLResponse(content=html_page_download(wc), status_code=200)

  os.makedirs('documents/'+dir_name)
  wc = ""

  log_list.append("Please find the logs for your transcription below:<br><br>")
  log_list.append("Files Uploaded: <br>")

  for i in files:
    log_list.append(i.filename+"<br>")

  log_list.append("<br>")

  for file in files:
    token = "d3b6f15c585b4a1bbf43f20f60535185"
    fname = file.filename

    tid = upload_file(token,file.file)
    result = {}
    log_list.append("starting to transcribe the file:&nbsp;&nbsp;"+fname+"<br>")
    print('starting to transcribe the file: &nbsp;&nbsp;[ {} ]'.format(fname))
    while result.get("status") != 'completed':
        print(result.get("status"))
        result = get_text(token, tid)
        # Handeling Errors
        if result.get("status") == 'error':
          log_list.append("Error occured while transcribing the file :&nbsp;&nbsp;"+fname+"<br>")
          shutil.make_archive("documents/"+dir_name,"zip","documents/"+dir_name)
          wc = wc+"<img src='/static/error.jpg' height='20'>&nbsp;&nbsp;Error &nbsp;:&nbsp;"+fname+"<br><br>"
          s3.upload_file("documents/"+dir_name+".zip","video-transcription-file-sharing","transcriptions/"+dir_name+".zip")
          os.remove("documents/"+dir_name+".zip")
          shutil.rmtree("documents/"+dir_name)
          return HTMLResponse(content=html_page_download(wc), status_code=200)

    log_list.append("Transcription Completed for the file:&nbsp;&nbsp;"+fname+"<br>")
    df = json_data_extraction(result,fname)
    print('saving transcript...')
    log_list.append("Saving the transcription of the file :&nbsp;&nbsp;"+fname+"<br>")

    df = df[['spcode','utter']]

    print('Converting files')
    log_list.append("Converting into document file:&nbsp;&nbsp;"+fname+"<br>")

    # open an existing document
    doc = docx.Document()

    t = doc.add_table(df.shape[0]+1, df.shape[1])

    # add the header rows.
    for j in range(df.shape[-1]):
        t.cell(0,j).text = df.columns[j]

    # add the rest of the data frame
    for i in range(df.shape[0]):
        for j in range(df.shape[-1]):
            t.cell(i+1,j).text = str(df.values[i,j])

    print('saving transcript...')
    log_list.append("Saving the document file:&nbsp;&nbsp;"+fname+"<br><br><br>")
    doc.save("documents/"+dir_name+"/"+fname+".docx")
    wc = wc+"<img src='/static/success.jpg' height='20'>&nbsp;&nbsp;Completed &nbsp;:&nbsp;"+fname+"<br><br>"

  log_list.append("Zipping all the transcribed documents and preparing to download")
  shutil.make_archive("documents/"+dir_name,"zip","documents/"+dir_name)
  s3.upload_file("documents/"+dir_name+".zip","video-transcription-file-sharing","transcriptions/"+dir_name+".zip")
  os.remove("documents/"+dir_name+".zip")
  shutil.rmtree("documents/"+dir_name)
  return HTMLResponse(content=html_page_download(wc), status_code=200)

@app.get('/download')
async def download():
  zip_url = boto3.client('s3').generate_presigned_url(ClientMethod='get_object', Params={'Bucket': 'video-transcription-file-sharing', 'Key': "transcriptions/"+dir_name+".zip"},ExpiresIn=360)
  return RedirectResponse(zip_url)

@app.get('/logs')
async def logs():
  logs = "".join(log_list)
  return HTMLResponse(content=html_page_logs(logs), status_code=200)