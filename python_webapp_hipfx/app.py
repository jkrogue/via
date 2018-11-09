from flask import Flask, request, render_template, send_file
import json
import pickle
import requests
from bs4 import BeautifulSoup
import dicom_image_tools
import pydicom
from PIL.Image import fromarray
from io import BytesIO

username = input('username for mpower: ')
password = input('password for mpower: ')

accessions = pickle.load(open(input('accessions pickel file to use: '),'rb'))

app = Flask(__name__)

#Get the CSRF_TOKEN from sign-in page
login_url = "https://mpower.radiology.ucsf.edu/accounts/login/?next=/"
session_requests = requests.session()

response = session_requests.get(login_url)

soup = BeautifulSoup(response.content,"html.parser")


authenticity_token = soup.find_all('input',{"name":"csrfmiddlewaretoken"})[0]['value']
print(authenticity_token)

#print(authenticity_token)

#my login info
login_info = {
    "username": username,
    "password": password,
    "csrfmiddlewaretoken": authenticity_token
}


#Login
response = session_requests.post(login_url, data = login_info, headers = dict(referer=login_url))

def parse_report(accession_number):
    mpower_link = "https://mpower.radiology.ucsf.edu/search/rad?q=" + accession_number
    response = session_requests.get(mpower_link, headers = dict(referer=mpower_link))

    soup = BeautifulSoup(response.content,"html.parser")
    
    #print(response.content)
    search_results = soup.find_all("div", class_="report-text")[0]

    return "{}".format(search_results)

def serve_pil_img(pil_img):
    """For future development of serving image directly from DICOM"""
    img_io = BytesIO()
    pil_img.save(img_io, 'JPEG', quality=70)
    img_io.seek(0)
    return send_file(img_io, mimetype='image/jpeg')

@app.route('/')
def via():
    return render_template('via.html', accessions=accessions)
    
@app.route('/report', methods=['POST','GET'])
def get_report():
    if request.method=='POST':
        result = request.form
        accession_number = result['accession']
        return parse_report(accession_number)

@app.route('/image')
def serve_img():
    """For future development of serving image directly from DICOM"""
    ds = pydicom.dcmread('E5482906S3I1.DCM')
    pixels = dicom_image_tools.trans_pixels(ds,ds.pixel_array)
    image = fromarray(pixels,mode="L")
    return serve_pil_img(image)



if __name__ == '__main__':
    app.run()