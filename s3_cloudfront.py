import os
import uuid
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

def get_cloudfront_distribution_id(domain):
    """Find CloudFront Distribution ID for the given domain."""
    try:
        response = cloudfront_client.list_distributions()
        for distribution in response.get("DistributionList", {}).get("Items", []):
            aliases = distribution.get("Aliases", {}).get("Items", [])
            if domain in aliases:
                return distribution["Id"]
        return None
    except Exception as e:
        return str(e)

@s3_bp.route('/api/uploads', methods=['POST'])
def upload_files():
    """Upload ZIP contents to S3 and invalidate CloudFront cache."""
    if 'file' not in request.files:
        return jsonify({"message": "No file uploaded.", "status": "error"}), 400

    file = request.files['file']
    bucket = request.form.get('bucket')
    domain = request.form.get('domain')

    if not bucket or not domain:
        return jsonify({"message": "Bucket Name and CloudFront Domain are required.", "status": "error"}), 400

    # Validate File Size (Max 10MB)
    if file.content_length > 10 * 1024 * 1024:
        return jsonify({"message": "File size exceeds 10MB limit.", "status": "error"}), 400

    # Create unique extraction folder
    extract_folder = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()))
    os.makedirs(extract_folder, exist_ok=True)

    # Save uploaded file
    zip_path = os.path.join(extract_folder, file.filename)
    file.save(zip_path)

    try:
        shutil.unpack_archive(zip_path, extract_folder)
    except Exception as e:
        return jsonify({"message": f"Invalid archive: {str(e)}", "status": "error"}), 400
    finally:
        os.remove(zip_path)

    # Step 1: Clear S3 bucket
    try:
        objects = s3_client.list_objects_v2(Bucket=bucket)
        if 'Contents' in objects:
            delete_keys = [{'Key': obj['Key']} for obj in objects['Contents']]
            s3_client.delete_objects(Bucket=bucket, Delete={'Objects': delete_keys})
    except Exception as e:
        return jsonify({"message": f"Failed to clear S3 bucket: {str(e)}", "status": "error"}), 400

    # Step 2: Upload extracted files to S3 (preserving folder structure)
    uploaded_files = []
    errors = []

    parent_folder = os.listdir(extract_folder)[0]
    full_parent_path = os.path.join(extract_folder, parent_folder)

    for root, _, files in os.walk(extract_folder):
        for filename in files:
            local_file_path = os.path.join(root, filename)
            s3_key = os.path.relpath(local_file_path, full_parent_path).replace("\\", "/")
            content_type = mimetypes.guess_type(local_file_path)[0] or "application/octet-stream"

            try:
                s3_client.upload_file(local_file_path, bucket, s3_key, ExtraArgs={"ContentType": content_type})
                uploaded_files.append({"filename": s3_key, "status": "uploaded"})
            except Exception as e:
                errors.append({"filename": s3_key, "error": str(e)})

    # Clean up
    shutil.rmtree(extract_folder, ignore_errors=True)

    # Step 3: Invalidate CloudFront cache
    distribution_id = get_cloudfront_distribution_id(domain)
    if not distribution_id:
        return jsonify({"message": f"CloudFront Distribution not found for domain {domain}.", "status": "error"}), 400

    try:
        response = cloudfront_client.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                "Paths": {"Quantity": 1, "Items": ["/*"]},
                "CallerReference": str(uuid.uuid4())
            }
        )
        cloudfront_status = {"invalidation_id": response["Invalidation"]["Id"], "status": "success"}
    except Exception as e:
        cloudfront_status = {"status": "error", "error": str(e)}

    return jsonify({
        "uploaded_files": uploaded_files,
        "errors": errors,
        "cloudfront_status": cloudfront_status,
        "message": "File upload and deployment completed.",
        "status": "success" if uploaded_files else "error"
    })



@s3_bp.route('/api/buckets', methods=['GET'])
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

@s3_bp.route('/api/domains', methods=['GET'])
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
