import requests
import os
import time
import json
import base64
from datetime import datetime
import xml.etree.ElementTree as ET
import hashlib
import hmac
import urllib.parse
import logging
from PIL import Image
import io

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("amazon_seller.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AmazonSellerAPI:
    def __init__(self, config_file=None):
        """Initialize the Amazon Seller API client."""
        self.config = {}
        if config_file and os.path.exists(config_file):
            with open(config_file, 'r') as f:
                self.config = json.load(f)
        else:
            # Prompt for credentials if config file doesn't exist
            self.config = {
                "seller_id": input("Enter your Amazon Seller ID: "),
                "access_key": input("Enter your Amazon MWS Access Key: "),
                "secret_key": input("Enter your Amazon MWS Secret Key: "),
                "marketplace_id": input("Enter your Marketplace ID (default US: A2EUQ1WTGCTBG2): ") or "A2EUQ1WTGCTBG2",
                "auth_token": input("Enter your MWS Auth Token: ")
            }
            save_config = input("Save these credentials for future use? (yes/no): ").lower()
            if save_config == "yes" or save_config == "y":
                with open("amazon_seller_config.json", 'w') as f:
                    json.dump(self.config, f)
                logger.info("Credentials saved to amazon_seller_config.json")
        
        self.base_url = "https://mws.amazonservices.com/"
        self.endpoint = "/Products/2011-10-01"
    
    def generate_signature(self, method, query_string):
        """Generate the authentication signature for Amazon MWS requests."""
        string_to_sign = f"{method}\nmws.amazonservices.com\n{self.endpoint}\n{query_string}"
        hmac_signature = hmac.new(
            self.config["secret_key"].encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(hmac_signature).decode('utf-8')
    
    def create_product_listing(self, product_details):
        """Create a new product listing on Amazon."""
        logger.info(f"Creating product listing for: {product_details['title']}")
        
        # Prepare the XML feed content for product submission
        feed_content = self._create_product_feed_xml(product_details)
        
        # Submit the feed to Amazon MWS
        feed_submission_id = self._submit_feed(feed_content, "_POST_PRODUCT_DATA_")
        
        if feed_submission_id:
            logger.info(f"Product feed submitted successfully. Feed Submission ID: {feed_submission_id}")
            
            # Monitor feed processing status
            status = self._monitor_feed_status(feed_submission_id)
            
            if status == "_DONE_":
                logger.info("Product listing created successfully!")
                return True
            else:
                logger.error(f"Feed processing ended with status: {status}")
                return False
        else:
            logger.error("Failed to submit product feed")
            return False
    
    def _create_product_feed_xml(self, product_details):
        """Create the XML feed for product submission."""
        root = ET.Element("AmazonEnvelope")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set("xsi:noNamespaceSchemaLocation", "amzn-envelope.xsd")
        
        # Header
        header = ET.SubElement(root, "Header")
        document_version = ET.SubElement(header, "DocumentVersion")
        document_version.text = "1.01"
        merchant_identifier = ET.SubElement(header, "MerchantIdentifier")
        merchant_identifier.text = self.config["seller_id"]
        
        # Message Type
        message_type = ET.SubElement(root, "MessageType")
        message_type.text = "Product"
        
        # Message
        message = ET.SubElement(root, "Message")
        message_id = ET.SubElement(message, "MessageID")
        message_id.text = "1"  # First message in this feed
        
        # Operation Type
        operation_type = ET.SubElement(message, "OperationType")
        operation_type.text = "Update"  # Use "Update" for both new items and updates
        
        # Product
        product = ET.SubElement(message, "Product")
        
        # SKU (required)
        sku = ET.SubElement(product, "SKU")
        sku.text = product_details["sku"]
        
        # Standard Product ID (UPC, EAN, ISBN, etc.)
        if "standard_product_id" in product_details:
            standard_product_id = ET.SubElement(product, "StandardProductID")
            
            id_type = ET.SubElement(standard_product_id, "Type")
            id_type.text = product_details["standard_product_id"]["type"]  # e.g., "UPC", "EAN", "ISBN"
            
            id_value = ET.SubElement(standard_product_id, "Value")
            id_value.text = product_details["standard_product_id"]["value"]
        
        # Product details
        product_data = ET.SubElement(product, "ProductData")
        
        # Product category - this example uses "CE" (Consumer Electronics)
        category = ET.SubElement(product_data, product_details.get("category", "CE"))
        
        # General product information that applies to all categories
        description_data = ET.SubElement(category, "ProductType")
        
        # Title (required)
        title = ET.SubElement(description_data, "Title")
        title.text = product_details["title"]
        
        # Brand (required for most categories)
        brand = ET.SubElement(description_data, "Brand")
        brand.text = product_details["brand"]
        
        # Description (required)
        description = ET.SubElement(description_data, "Description")
        description.text = product_details["description"]
        
        # Bullet points (recommended)
        if "bullet_points" in product_details:
            for point in product_details["bullet_points"]:
                bullet = ET.SubElement(description_data, "BulletPoint")
                bullet.text = point
        
        # Item dimensions
        if "dimensions" in product_details:
            item_dimensions = ET.SubElement(description_data, "ItemDimensions")
            
            length = ET.SubElement(item_dimensions, "Length")
            length.set("unitOfMeasure", "inches")
            length.text = str(product_details["dimensions"]["length"])
            
            width = ET.SubElement(item_dimensions, "Width")
            width.set("unitOfMeasure", "inches")
            width.text = str(product_details["dimensions"]["width"])
            
            height = ET.SubElement(item_dimensions, "Height")
            height.set("unitOfMeasure", "inches")
            height.text = str(product_details["dimensions"]["height"])
            
            weight = ET.SubElement(item_dimensions, "Weight")
            weight.set("unitOfMeasure", "pounds")
            weight.text = str(product_details["dimensions"]["weight"])
        
        # Convert to string
        tree = ET.ElementTree(root)
        xml_string = ET.tostring(root, encoding="utf-8", method="xml")
        
        return xml_string
    
    def _submit_feed(self, feed_content, feed_type):
        """Submit a feed to Amazon MWS."""
        params = {
            "Action": "SubmitFeed",
            "Version": "2009-01-01",
            "Merchant": self.config["seller_id"],
            "SignatureVersion": "2",
            "SignatureMethod": "HmacSHA256",
            "Timestamp": datetime.utcnow().isoformat(),
            "AWSAccessKeyId": self.config["access_key"],
            "FeedType": feed_type,
            "PurgeAndReplace": "false",
            "MWSAuthToken": self.config["auth_token"]
        }
        
        # Sort parameters for signature
        sorted_params = sorted(params.items(), key=lambda x: x[0])
        query_string = "&".join([f"{k}={urllib.parse.quote(v, safe='')}" for k, v in sorted_params])
        
        # Generate signature
        signature = self.generate_signature("POST", query_string)
        
        # Add signature to parameters
        params["Signature"] = signature
        
        try:
            headers = {
                "Content-Type": "application/xml",
                "Content-MD5": base64.b64encode(hashlib.md5(feed_content).digest()).decode('utf-8')
            }
            
            response = requests.post(
                f"{self.base_url}?{query_string}&Signature={urllib.parse.quote(signature, safe='')}",
                data=feed_content,
                headers=headers
            )
            
            if response.status_code == 200:
                # Parse XML response to get FeedSubmissionId
                root = ET.fromstring(response.text)
                namespace = {"ns": "http://mws.amazonaws.com/doc/2009-01-01/"}
                feed_submission_id = root.find(".//ns:FeedSubmissionId", namespace).text
                return feed_submission_id
            else:
                logger.error(f"Feed submission failed with status code: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
        
        except Exception as e:
            logger.error(f"Exception during feed submission: {str(e)}")
            return None
    
    def _monitor_feed_status(self, feed_submission_id, max_attempts=10):
        """Monitor the status of a submitted feed."""
        logger.info(f"Monitoring feed submission status for ID: {feed_submission_id}")
        
        attempts = 0
        while attempts < max_attempts:
            status = self._get_feed_submission_status(feed_submission_id)
            
            if status in ["_DONE_", "_CANCELLED_", "_FAILED_"]:
                return status
            
            logger.info(f"Feed processing status: {status}. Waiting before checking again...")
            attempts += 1
            time.sleep(60)  # Wait for 60 seconds before checking again
        
        logger.warning(f"Reached maximum monitoring attempts. Last status: {status}")
        return status
    
    def _get_feed_submission_status(self, feed_submission_id):
        """Get the status of a feed submission."""
        params = {
            "Action": "GetFeedSubmissionResult",
            "Version": "2009-01-01",
            "Merchant": self.config["seller_id"],
            "SignatureVersion": "2",
            "SignatureMethod": "HmacSHA256",
            "Timestamp": datetime.utcnow().isoformat(),
            "AWSAccessKeyId": self.config["access_key"],
            "FeedSubmissionId": feed_submission_id,
            "MWSAuthToken": self.config["auth_token"]
        }
        
        # Sort parameters for signature
        sorted_params = sorted(params.items(), key=lambda x: x[0])
        query_string = "&".join([f"{k}={urllib.parse.quote(v, safe='')}" for k, v in sorted_params])
        
        # Generate signature
        signature = self.generate_signature("POST", query_string)
        
        try:
            response = requests.post(
                f"{self.base_url}?{query_string}&Signature={urllib.parse.quote(signature, safe='')}",
                headers={"Content-Type": "application/xml"}
            )
            
            if response.status_code == 200:
                # Parse XML response to get ProcessingStatus
                root = ET.fromstring(response.text)
                namespace = {"ns": "http://mws.amazonaws.com/doc/2009-01-01/"}
                status = root.find(".//ns:ProcessingStatus", namespace).text
                return status
            else:
                logger.error(f"Failed to get feed status. Status code: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
        
        except Exception as e:
            logger.error(f"Exception while getting feed status: {str(e)}")
            return None
    
    def update_inventory(self, sku, quantity, price):
        """Update inventory quantity and price for a product."""
        logger.info(f"Updating inventory for SKU: {sku}, Quantity: {quantity}, Price: {price}")
        
        # Create inventory feed XML
        inventory_feed = self._create_inventory_feed(sku, quantity, price)
        
        # Submit the feed
        feed_submission_id = self._submit_feed(inventory_feed, "_POST_INVENTORY_AVAILABILITY_DATA_")
        
        if feed_submission_id:
            logger.info(f"Inventory feed submitted successfully. Feed Submission ID: {feed_submission_id}")
            
            # Monitor feed processing status
            status = self._monitor_feed_status(feed_submission_id)
            
            if status == "_DONE_":
                logger.info("Inventory updated successfully!")
                return True
            else:
                logger.error(f"Feed processing ended with status: {status}")
                return False
        else:
            logger.error("Failed to submit inventory feed")
            return False
    
    def _create_inventory_feed(self, sku, quantity, price):
        """Create XML feed for inventory update."""
        root = ET.Element("AmazonEnvelope")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set("xsi:noNamespaceSchemaLocation", "amzn-envelope.xsd")
        
        # Header
        header = ET.SubElement(root, "Header")
        document_version = ET.SubElement(header, "DocumentVersion")
        document_version.text = "1.01"
        merchant_identifier = ET.SubElement(header, "MerchantIdentifier")
        merchant_identifier.text = self.config["seller_id"]
        
        # Message Type
        message_type = ET.SubElement(root, "MessageType")
        message_type.text = "Inventory"
        
        # Message
        message = ET.SubElement(root, "Message")
        message_id = ET.SubElement(message, "MessageID")
        message_id.text = "1"
        
        # Inventory
        inventory = ET.SubElement(message, "Inventory")
        
        # SKU
        sku_element = ET.SubElement(inventory, "SKU")
        sku_element.text = sku
        
        # Quantity
        quantity_element = ET.SubElement(inventory, "Quantity")
        quantity_element.text = str(quantity)
        
        # Price
        price_element = ET.SubElement(inventory, "Price")
        price_element.text = str(price)
        
        # Convert to string
        xml_string = ET.tostring(root, encoding="utf-8", method="xml")
        
        return xml_string
    
    def upload_product_image(self, sku, image_path):
        """Upload a product image to Amazon."""
        logger.info(f"Uploading image for SKU: {sku}")
        
        # Check if image exists
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return False
        
        # Validate image
        try:
            with Image.open(image_path) as img:
                # Check dimensions (Amazon requires at least 500x500 pixels)
                width, height = img.size
                if width < 500 or height < 500:
                    logger.warning(f"Image dimensions ({width}x{height}) are below Amazon's recommended minimum of 500x500 pixels")
        except Exception as e:
            logger.error(f"Error validating image: {str(e)}")
            return False
        
        # Create image feed XML
        with open(image_path, 'rb') as f:
            image_data = f.read()
            image_feed = self._create_image_feed(sku, image_path)
        
        # Submit the feed
        feed_submission_id = self._submit_feed(image_feed, "_POST_PRODUCT_IMAGE_DATA_")
        
        if feed_submission_id:
            logger.info(f"Image feed submitted successfully. Feed Submission ID: {feed_submission_id}")
            
            # Monitor feed processing status
            status = self._monitor_feed_status(feed_submission_id)
            
            if status == "_DONE_":
                logger.info("Image uploaded successfully!")
                return True
            else:
                logger.error(f"Feed processing ended with status: {status}")
                return False
        else:
            logger.error("Failed to submit image feed")
            return False
    
    def _create_image_feed(self, sku, image_path):
        """Create XML feed for image upload."""
        root = ET.Element("AmazonEnvelope")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set("xsi:noNamespaceSchemaLocation", "amzn-envelope.xsd")
        
        # Header
        header = ET.SubElement(root, "Header")
        document_version = ET.SubElement(header, "DocumentVersion")
        document_version.text = "1.01"
        merchant_identifier = ET.SubElement(header, "MerchantIdentifier")
        merchant_identifier.text = self.config["seller_id"]
        
        # Message Type
        message_type = ET.SubElement(root, "MessageType")
        message_type.text = "ProductImage"
        
        # Message
        message = ET.SubElement(root, "Message")
        message_id = ET.SubElement(message, "MessageID")
        message_id.text = "1"
        
        # Product Image
        product_image = ET.SubElement(message, "ProductImage")
        
        # SKU
        sku_element = ET.SubElement(product_image, "SKU")
        sku_element.text = sku
        
        # Image Type (Main, PT, ALTO, etc.)
        image_type = ET.SubElement(product_image, "ImageType")
        image_type.text = "Main"  # Primary product image
        
        # Image Location (URL to image)
        # Note: For direct uploads, Amazon requires a URL. For this script, we'd need to either:
        # 1. Have the image already hosted somewhere, or
        # 2. Use Amazon's S3 or another service to host the image before referencing it here
        image_location = ET.SubElement(product_image, "ImageLocation")
        image_location.text = image_path  # This would be a URL in real usage
        
        # Convert to string
        xml_string = ET.tostring(root, encoding="utf-8", method="xml")
        
        return xml_string

    def get_order_metrics(self, start_date, end_date):
        """Get order metrics for a date range."""
        logger.info(f"Getting order metrics from {start_date} to {end_date}")
        
        # Implementation would fetch metrics from Amazon's API
        # This is a placeholder method showing what data might be returned
        return {
            "total_orders": 0,
            "total_revenue": 0.00,
            "average_order_value": 0.00,
            "return_rate": 0.00
        }


def collect_product_info():
    """Collect product information from user input."""
    print("\n=== Amazon Seller Product Creation ===")
    print("Please enter details about the product you want to sell:\n")
    
    product_details = {
        "sku": input("Enter a unique SKU for your product: "),
        "title": input("Enter product title: "),
        "brand": input("Enter brand name: "),
        "description": input("Enter product description: "),
        "category": input("Enter product category (default: CE for Consumer Electronics): ") or "CE",
        "bullet_points": []
    }
    
    # Collect bullet points
    print("\nEnter up to 5 bullet points (leave blank to stop):")
    for i in range(5):
        bullet = input(f"Bullet point {i+1}: ")
        if not bullet:
            break
        product_details["bullet_points"].append(bullet)
    
    # Collect standard product ID
    has_standard_id = input("\nDo you have a UPC, EAN, or ISBN for this product? (yes/no): ").lower()
    if has_standard_id in ["yes", "y"]:
        id_type = input("Enter ID type (UPC, EAN, ISBN): ").upper()
        id_value = input(f"Enter {id_type} value: ")
        product_details["standard_product_id"] = {
            "type": id_type,
            "value": id_value
        }
    
    # Collect dimensions
    print("\nEnter product dimensions:")
    product_details["dimensions"] = {
        "length": float(input("Length (inches): ")),
        "width": float(input("Width (inches): ")),
        "height": float(input("Height (inches): ")),
        "weight": float(input("Weight (pounds): "))
    }
    
    # Collect pricing and inventory
    print("\nEnter pricing and inventory information:")
    product_details["price"] = float(input("Price ($): "))
    product_details["quantity"] = int(input("Initial quantity available: "))
    
    # Collect image information
    has_image = input("\nDo you have a product image to upload? (yes/no): ").lower()
    if has_image in ["yes", "y"]:
        product_details["image_path"] = input("Enter path to product image file: ")
    
    return product_details


def main():
    """Main function to run the Amazon seller program."""
    print("=" * 50)
    print("Amazon Seller Product Listing Tool")
    print("=" * 50)
    print("\nThis program helps you create product listings on Amazon Seller Central")
    print("You'll need your Amazon Seller credentials to proceed.")
    
    # Initialize API client
    config_file = "amazon_seller_config.json"
    if os.path.exists(config_file):
        use_existing = input(f"Use existing configuration from {config_file}? (yes/no): ").lower()
        if use_existing != "yes" and use_existing != "y":
            config_file = None
    else:
        config_file = None
    
    amazon_api = AmazonSellerAPI(config_file)
    
    # Collect product information
    product_details = collect_product_info()
    
    # Create product listing
    if amazon_api.create_product_listing(product_details):
        print("\nProduct listing created successfully!")
        
        # Update inventory and price
        if amazon_api.update_inventory(product_details["sku"], product_details["quantity"], product_details["price"]):
            print("Inventory and price updated successfully!")
        else:
            print("Failed to update inventory and price.")
        
        # Upload product image if provided
        if "image_path" in product_details:
            if amazon_api.upload_product_image(product_details["sku"], product_details["image_path"]):
                print("Product image uploaded successfully!")
            else:
                print("Failed to upload product image.")
        
        print("\nYour product is now listed on Amazon!")
        print("You can check the status in your Amazon Seller Central account.")
    else:
        print("\nFailed to create product listing. Check the logs for details.")
    
    print("\nThank you for using the Amazon Seller Product Listing Tool!")


if __name__ == "__main__":
    main()