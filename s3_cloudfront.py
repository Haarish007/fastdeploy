from concurrent.futures import ThreadPoolExecutor
import io
import os
import uuid
import zipfile
import boto3
import mimetypes
import shutil
from flask import Blueprint, request, jsonify

# Initialize blueprint
s3_bp = Blueprint('s3_bp', __name__)

# AWS Clients
s3_client = boto3.client("s3")
cloudfront_client = boto3.client("cloudfront")

# Upload folder path
UPLOAD_FOLDER = "/tmp/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_cloudfront_distribution_id(domain, bucket):
    try:
        response = cloudfront_client.list_distributions()
        distributions = response.get("DistributionList", {}).get("Items", [])

        for distribution in distributions:
            aliases = distribution.get("Aliases", {}).get("Items", [])
            if domain in aliases:
                for origin in distribution.get("Origins", {}).get("Items", []):
                    domain_name = origin.get("DomainName", "")
                    expected_origin = f"{bucket}.s3.ap-south-1.amazonaws.com"

                    if domain_name == expected_origin:
                        return distribution["Id"]

                return {
                    "error": "Bucket mismatch",
                    "message": f"Bucket '{bucket}' does not match the origin of '{domain}'"
                }

        return {
            "error": "Distribution not found",
            "message": f"No distribution found for domain '{domain}'"
        }

    except Exception as e:
        return {
            "error": "Exception",
            "message": str(e)
        }




@s3_bp.route('/uploads', methods=['POST'])
def upload_files():
    file = request.files.get('file')
    bucket = request.form.get('bucket')
    domain = request.form.get('domain')

    if not file or not bucket or not domain:
        return jsonify({"message": "File, bucket, and domain are required.", "status": "error"}), 400

    if file.content_length > 10 * 1024 * 1024:
        return jsonify({"message": "File size exceeds 10MB limit.", "status": "error"}), 400

    try:
        zip_bytes = io.BytesIO(file.read())
        zipfile_obj = zipfile.ZipFile(zip_bytes)
    except Exception as e:
        return jsonify({"message": f"Invalid zip file: {str(e)}", "status": "error"}), 200

    distribution_check = get_cloudfront_distribution_id(domain, bucket)
    if isinstance(distribution_check, dict) and distribution_check.get("error"):
        return jsonify({
            "status": "error",
            "message": distribution_check.get("message") or distribution_check.get("error")
        }), 200

    distribution_id = distribution_check

    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket)

        keys_to_delete = []
        for page in pages:
            for obj in page.get('Contents', []):
                keys_to_delete.append({'Key': obj['Key']})

        if keys_to_delete:
            for i in range(0, len(keys_to_delete), 1000):
                s3_client.delete_objects(
                    Bucket=bucket,
                    Delete={'Objects': keys_to_delete[i:i + 1000]}
                )
    except Exception as e:
        return jsonify({"message": f"Failed to clear existing files: {str(e)}", "status": "error"}), 500

    uploaded_files = []
    errors = []

    def upload_file(zip_info):
        key = "/".join(zip_info.filename.split("/")[1:])
        if key.endswith("/"):
            return
        try:
            content = zipfile_obj.read(zip_info)
            content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
            s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=content,
                ContentType=content_type
            )
            uploaded_files.append({"filename": key, "status": "uploaded"})
        except Exception as e:
            errors.append({"filename": key, "error": str(e)})

    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(upload_file, zipfile_obj.infolist())

    try:
        response = cloudfront_client.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                "Paths": {"Quantity": 1, "Items": ["/*"]},
                "CallerReference": str(uuid.uuid4())
            }
        )
        cloudfront_status = {
            "invalidation_id": response["Invalidation"]["Id"],
            "status": "invalidated"
        }
    except Exception as e:
        cloudfront_status = {"status": "error", "error": str(e)}

    status = "success" if not errors and cloudfront_status.get("status") != "error" else "error"
    return jsonify({
        "status": status,
        "message": "🚀 Deployment successful! All files have been uploaded and are ready to serve." if status == "success" else "Some errors occurred",
        "uploaded_files": uploaded_files,
        "errors": errors,
        "cloudfront_status": cloudfront_status
    }), 200

@s3_bp.route('/buckets', methods=['GET'])
def list_buckets():
    """Return all available S3 buckets."""
    try:
        response = s3_client.list_buckets()
        buckets = [bucket['Name'] for bucket in response.get('Buckets', [])]
        return jsonify({
            "data": buckets,
            "message": "fetch buckets",
            "status": "success" if buckets else "error"
        })
    except Exception as e:
        return jsonify({
            "data": [],
            "message": str(e),
            "status": "error"
        })

@s3_bp.route('/domains', methods=['GET'])
def list_domains():
    """Return all CloudFront alternate domains."""
    try:
        response = cloudfront_client.list_distributions()
        domains = []
        for distribution in response.get("DistributionList", {}).get("Items", []):
            if 'Aliases' in distribution and 'Items' in distribution['Aliases']:
                domains.extend(distribution['Aliases']['Items'])
        return jsonify({
            "data": domains,
            "message": "fetch domains",
            "status": "success" if domains else "error"
        })
    except Exception as e:
        return jsonify({
            "data": [],
            "message": str(e),
            "status": "error"
        })
