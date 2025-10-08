#!/usr/bin/env python3
"""
Jira Automation Main Script
Orchestrates the complete workflow: JumpCloud login -> Jira export -> Google Sheets upload
"""
import logging
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.settings import settings
from src.automation.web_driver import WebDriverManager
from src.auth.jumpcloud_auth import JumpCloudAuth
from src.jira.operations import JiraOperations
from src.utils.file_operations import FileOperations

class JiraAutomationWorkflow:
    """Main workflow orchestrator for Jira automation."""

    def __init__(self):
        """Initialize the automation workflow."""
        self.driver_manager = WebDriverManager()
        self.driver = None
        self.file_ops = FileOperations()

        # Setup logging
        self._setup_logging()

        # Validate configuration
        self._validate_configuration()

    def _setup_logging(self):
        """Setup logging configuration."""
        log_file = settings.LOGS_FOLDER / "jira_automation.log"

        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                            handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)])

        self.logger = logging.getLogger(__name__)

    def _validate_configuration(self):
        """Validate that all required configuration is available."""
        try:
            settings.validate_credentials()
            self.logger.info("Success: Configuration validation passed")
        except ValueError as e:
            self.logger.error(f"ERROR:Configuration validation failed: {e}")
            raise

    def run_full_workflow(self):
        """Execute the complete automation workflow."""
        try:
            self.logger.info("Starting: Starting Jira Automation Workflow")

            # Step 1: Setup WebDriver
            self.driver = self._setup_webdriver()

            # Step 2: Authenticate with JumpCloud
            self._authenticate_jumpcloud()

            # Step 3: Navigate to Jira and export data
            exported_file = self._export_jira_data()

            self.logger.info("Workflow completed successfully!")
            return True

        except Exception as e:
            self.logger.error(f"ERROR:Workflow failed: {e}")
            return False
        finally:
            self._cleanup()

    def _setup_webdriver(self):
        """Setup and return WebDriver instance."""
        self.logger.info("Setting up WebDriver...")
        return self.driver_manager.setup_driver()

    def _authenticate_jumpcloud(self):
        """Authenticate with JumpCloud."""
        self.logger.info("Authenticating with JumpCloud...")

        auth = JumpCloudAuth(self.driver)

        if not auth.login():
            raise Exception("JumpCloud authentication failed")

        # Navigate to Jira
        auth.navigate_to_jira()
        self.logger.info("Success: JumpCloud authentication and Jira navigation completed")

    def _export_jira_data(self):
        """Export data from Jira using JQL query."""
        self.logger.info("Exporting Jira data...")

        jira_ops = JiraOperations(self.driver)

        exported_file = jira_ops.execute_jql_and_export(jira_url=settings.JIRA_SEARCH_URL, jql_query=settings.JQL_QUERY)

        if not exported_file or not exported_file.exists():
            raise Exception("Jira export failed - no file was created")

        self.logger.info(f"Success: Jira data exported to: {exported_file}")
        return exported_file

    def _cleanup(self):
        """Cleanup resources."""
        if self.driver:
            self.logger.info("Cleaning up...")
            self.driver_manager.close_driver()

        # Optional: Clean old files
        try:
            deleted_count = self.file_ops.clean_old_files(directory_path=settings.DOWNLOADS_FOLDER, max_age_days=7,
                                                          pattern="*.csv")
            if deleted_count > 0:
                self.logger.info(f"🗑Cleaned {deleted_count} old CSV files")
        except Exception as e:
            self.logger.warning(f"⚠File cleanup failed: {e}")

    def run_jira_export_only(self):
        """Run only the Jira export part of the workflow."""
        try:
            self.logger.info("Running Jira export only...")

            self.driver = self._setup_webdriver()
            self._authenticate_jumpcloud()
            exported_file = self._export_jira_data()

            self.logger.info(f"Success: Jira export completed: {exported_file}")
            return exported_file

        except Exception as e:
            self.logger.error(f"Jira export failed: {e}")
            raise
        finally:
            self._cleanup()


def main():
    """Main entry point for the application."""
    import argparse

    parser = argparse.ArgumentParser(description="Jira Automation Workflow")
    parser.add_argument('--mode', choices=['full', 'export-only'], default='full',
                        help='Workflow mode (default: full)')
    parser.add_argument('--file', help='CSV file path for upload-only mode')

    args = parser.parse_args()

    # Initialize workflow
    workflow = JiraAutomationWorkflow()

    try:
        if args.mode == 'full':
            success = workflow.run_full_workflow()
        elif args.mode == 'export-only':
            workflow.run_jira_export_only()
            success = True

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n⏹️ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR:Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
