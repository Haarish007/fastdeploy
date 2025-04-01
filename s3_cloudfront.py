from flask import Blueprint, request, redirect, url_for, flash, jsonify
import boto3
import os
import mimetypes
import shutil

s3_bp = Blueprint('s3', __name__)


s3_client = boto3.client("s3")
cloudfront_client = boto3.client("cloudfront")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@s3_bp.route('/upload', methods=['POST'])
def upload_files():
    data = request.get_json()

    if not data:
        return jsonify({"message": "Invalid request. JSON payload required.", "status": "error"}), 400

    bucket_name = data.get('bucket_name')
    cloudfront_domain = data.get('cloudfront_domain')
    files = request.files.getlist('files')

    if not bucket_name or not cloudfront_domain:
        return jsonify({"message": "Bucket Name and CloudFront Domain are required.", "status": "error"}), 400

    if not files:
        return jsonify({"message": "No files selected for upload.", "status": "error"}), 400

    uploaded_files, errors = [], []

    for file in files:
        if not file.filename:
            continue

        local_file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(local_file_path)

        content_type = mimetypes.guess_type(local_file_path)[0] or "application/octet-stream"

        try:
            s3_client.upload_file(local_file_path, bucket_name, file.filename, ExtraArgs={"ContentType": content_type})
            os.remove(local_file_path)
            uploaded_files.append({"filename": file.filename, "status": "uploaded"})
        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)})

    # Clean up the upload folder
    if not os.listdir(UPLOAD_FOLDER):
        shutil.rmtree(UPLOAD_FOLDER, ignore_errors=True)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # Create CloudFront invalidation
    try:
        response = cloudfront_client.create_invalidation(
            DistributionId=cloudfront_domain,
            InvalidationBatch={
                "Paths": {"Quantity": 1, "Items": ["/*"]},
                "CallerReference": str(os.urandom(16))
            }
        )
        cloudfront_status = {"invalidation_id": response["Invalidation"]["Id"], "status": "success"}
    except Exception as e:
        cloudfront_status = {"status": "error", "error": str(e)}

    return jsonify({
        "uploaded_files": uploaded_files,
        "errors": errors,
        "cloudfront_status": cloudfront_status,
        "message": "File upload process completed.",
        "status": "success" if uploaded_files else "error"
    })

@s3_bp.route('/buckets', methods=['GET'])
def list_buckets():
    """Returns a list of S3 bucket names"""
    response = s3_client.list_buckets()
    buckets = [bucket['Name'] for bucket in response['Buckets']]
    if buckets:
        return jsonify({
            "data": buckets,
            "message": "fetch products fees",
            "status": "success"
        })
    else:
        return jsonify({
            "data": [],
            "message": "S3 buckets do not exist",
            "status": "error"
        })

@s3_bp.route('/domains', methods=['GET'])
def list_cloudfront_domains():
    """Returns a list of CloudFront alternate domain names"""
    response = cloudfront_client.list_distributions()
    domains = []
    for distribution in response['DistributionList']['Items']:
        if 'Aliases' in distribution and 'Items' in distribution['Aliases']:
            domains.extend(distribution['Aliases']['Items'])
    if domains:
        return jsonify({
            "data": domains,
            "message": "fetch products fees",
            "status": "success"
        })
    else:
        return jsonify({
            "data": [],
            "message": "CloudFront domains do not exist",
            "status": "error"
        })