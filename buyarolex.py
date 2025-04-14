from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import getpass
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FlipkartRolexBuyer:
    def __init__(self):
        # Set up Chrome options
        self.chrome_options = Options()
        # Uncomment the line below if you want to run in headless mode
        # self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument("--disable-notifications")
        
        # Initialize the Chrome driver
        self.service = Service("chromedriver")  # Make sure chromedriver is in PATH or specify path
        self.driver = webdriver.Chrome(service=self.service, options=self.chrome_options)
        self.wait = WebDriverWait(self.driver, 15)

    def login_to_flipkart(self, email, password):
        """Login to Flipkart with the given credentials"""
        try:
            logger.info("Logging into Flipkart...")
            self.driver.get("https://www.flipkart.com/")
            
            # Check for and close login popup if it appears
            try:
                close_button = self.wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//button[@class='_2KpZ6l _2doB4z']")))
                close_button.click()
                
                # Now click on the login button
                login_button = self.wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//a[text()='Login']")))
                login_button.click()
            except:
                # Login popup might already be showing
                pass
            
            # Enter email/phone
            email_input = self.wait.until(EC.presence_of_element_located(
                (By.XPATH, "//input[@class='_2IX_2- VJZDxU']")))
            email_input.send_keys(email)
            
            # Enter password
            password_input = self.driver.find_element(By.XPATH, "//input[@type='password']")
            password_input.send_keys(password)
            
            # Click submit
            submit_button = self.driver.find_element(By.XPATH, "//button[@type='submit' and contains(@class, '_2KpZ6l')]")
            submit_button.click()
            
            # Wait for login to complete
            time.sleep(3)
            logger.info("Login successful!")
            return True
        
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            return False

    def search_for_rolex(self):
        """Search for Rolex watches on Flipkart"""
        try:
            logger.info("Searching for Rolex watches...")
            search_box = self.wait.until(EC.presence_of_element_located(
                (By.NAME, "q")))
            search_box.clear()
            search_box.send_keys("Rolex watch")
            search_box.send_keys(Keys.RETURN)
            
            # Wait for search results to load
            self.wait.until(EC.presence_of_element_located(
                (By.XPATH, "//div[contains(@class, '_1YokD2')]")))
            logger.info("Search results loaded!")
            return True
        
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return False

    def filter_results(self):
        """Apply filters to find premium watches"""
        try:
            logger.info("Applying filters...")
            
            # Sort by price high to low (to find premium models first)
            sort_dropdown = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//div[text()='Popularity']")))
            sort_dropdown.click()
            
            # Click on "Price -- High to Low" option
            price_high_to_low = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//div[text()='Price -- High to Low']")))
            price_high_to_low.click()
            
            # Wait for the results to refresh
            time.sleep(3)
            logger.info("Filters applied successfully!")
            return True
        
        except Exception as e:
            logger.error(f"Filter application failed: {str(e)}")
            return False

    def select_rolex_watch(self):
        """Select the first available Rolex watch"""
        try:
            logger.info("Selecting a Rolex watch...")
            
            # Select the first product that appears to be a genuine Rolex
            watches = self.wait.until(EC.presence_of_all_elements_located(
                (By.XPATH, "//div[contains(@class, '_4ddWXP')]")))
            
            if not watches:
                watches = self.driver.find_elements(By.XPATH, "//div[contains(@class, '_1AtVbE')]//div[contains(@class, '_13oc-S')]")
            
            if watches:
                # Click on the first watch
                watches[0].click()
                
                # Switch to new tab (product opens in new tab)
                self.driver.switch_to.window(self.driver.window_handles[1])
                
                # Wait for product page to load
                self.wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(@class, 'aMaAEs')]")))
                
                logger.info("Selected a Rolex watch!")
                return True
            else:
                logger.error("No watches found in search results")
                return False
        
        except Exception as e:
            logger.error(f"Watch selection failed: {str(e)}")
            return False

    def add_to_cart(self):
        """Add the selected watch to cart"""
        try:
            logger.info("Adding watch to cart...")
            
            # Find and click the "ADD TO CART" button
            add_to_cart_btn = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[text()='ADD TO CART']")))
            add_to_cart_btn.click()
            
            # Wait for the item to be added to cart
            self.wait.until(EC.presence_of_element_located(
                (By.XPATH, "//div[contains(@class, '_3vIvU_')]")))
            
            logger.info("Watch added to cart successfully!")
            return True
        
        except Exception as e:
            logger.error(f"Adding to cart failed: {str(e)}")
            return False

    def proceed_to_checkout(self):
        """Proceed to checkout"""
        try:
            logger.info("Proceeding to checkout...")
            
            # Click the "Place Order" button
            place_order_btn = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[text()='Place Order']")))
            place_order_btn.click()
            
            # Wait for the delivery address page
            self.wait.until(EC.presence_of_element_located(
                (By.XPATH, "//div[contains(@class, '_1P2KH6')]")))
            
            logger.info("Reached checkout page!")
            return True
        
        except Exception as e:
            logger.error(f"Checkout process failed: {str(e)}")
            return False

    def enter_shipping_details(self, address_info):
        """Enter shipping information"""
        try:
            logger.info("Entering shipping details...")
            
            # Check if we need to add a new address or select existing
            try:
                # Try to click on "Add a new address" if it exists
                new_address_btn = self.wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//div[text()='Add a new address']")))
                new_address_btn.click()
                
                # Fill in the address form
                name_input = self.wait.until(EC.presence_of_element_located(
                    (By.NAME, "name")))
                name_input.send_keys(address_info["name"])
                
                phone_input = self.driver.find_element(By.NAME, "phone")
                phone_input.send_keys(address_info["phone"])
                
                pincode_input = self.driver.find_element(By.NAME, "pincode")
                pincode_input.send_keys(address_info["pincode"])
                
                address_input = self.driver.find_element(By.NAME, "addressLine1")
                address_input.send_keys(address_info["address"])
                
                city_input = self.driver.find_element(By.NAME, "city")
                city_input.send_keys(address_info["city"])
                
                # Select state from dropdown
                state_dropdown = self.driver.find_element(By.NAME, "state")
                state_dropdown.click()
                state_option = self.wait.until(EC.element_to_be_clickable(
                    (By.XPATH, f"//li[text()='{address_info['state']}']")))
                state_option.click()
                
                # Mark as home address
                home_radio = self.driver.find_element(By.XPATH, "//div[text()='Home']")
                home_radio.click()
                
                # Save address
                save_btn = self.driver.find_element(By.XPATH, "//button[text()='Save']")
                save_btn.click()
                
            except TimeoutException:
                # Might already have addresses, select the first one
                address_radio = self.wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//div[contains(@class, '_1XFPmK')]//input")))
                address_radio.click()
            
            # Click on "Deliver Here" button
            deliver_btn = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[text()='Deliver Here']")))
            deliver_btn.click()
            
            logger.info("Shipping details entered!")
            return True
        
        except Exception as e:
            logger.error(f"Entering shipping details failed: {str(e)}")
            return False

    def select_payment_method(self):
        """Select payment method and complete order"""
        try:
            logger.info("Selecting payment method...")
            
            # Wait for payment options to load
            self.wait.until(EC.presence_of_element_located(
                (By.XPATH, "//div[contains(@class, '_3IgmGS')]")))
            
            # Select "Cash on Delivery" (since we're just demonstrating)
            try:
                cod_option = self.wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//div[text()='Cash on Delivery']")))
                cod_option.click()
                
                # Click on "CONFIRM ORDER" button if available
                confirm_btn = self.wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//button[text()='CONFIRM ORDER']")))
                confirm_btn.click()
                
                # Wait for order confirmation
                self.wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(text(), 'Thank you')]")))
                
                logger.info("Order placed successfully!")
                return True
            
            except:
                logger.info("COD not available, selecting card payment...")
                card_option = self.wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//div[contains(text(), 'Credit / Debit / ATM Card')]")))
                card_option.click()
                
                # At this point we would need to enter card details
                # But for demonstration purposes, we'll stop here
                logger.info("Reached payment gateway. Demo stopping here.")
                return True
        
        except Exception as e:
            logger.error(f"Payment selection failed: {str(e)}")
            return False

    def complete_purchase(self):
        """Run the full purchase flow"""
        try:
            # Get credentials (in a real script, consider using a config file or env vars)
            email = input("Enter your Flipkart email or phone: ")
            password = getpass.getpass("Enter your Flipkart password: ")
            
            # Address information
            address_info = {
                "name": input("Enter full name: "),
                "phone": input("Enter phone number: "),
                "pincode": input("Enter pincode: "),
                "address": input("Enter address line: "),
                "city": input("Enter city: "),
                "state": input("Enter state: ")
            }
            
            # Execute the purchase flow
            if not self.login_to_flipkart(email, password):
                return False
            
            if not self.search_for_rolex():
                return False
            
            if not self.filter_results():
                return False
            
            if not self.select_rolex_watch():
                return False
            
            if not self.add_to_cart():
                return False
            
            if not self.proceed_to_checkout():
                return False
            
            if not self.enter_shipping_details(address_info):
                return False
            
            if not self.select_payment_method():
                return False
            
            logger.info("Purchase process completed!")
            return True
        
        except Exception as e:
            logger.error(f"Purchase process failed: {str(e)}")
            return False
        
        finally:
            input("Press Enter to close the browser...")
            self.driver.quit()


if __name__ == "__main__":
    print("=== Flipkart Rolex Purchase Automation ===")
    print("NOTE: This is a demonstration script. No actual purchase will be made.")
    print("The script will stop at the payment stage.")
    print("=" * 40)
    
    buyer = FlipkartRolexBuyer()
    buyer.complete_purchase()