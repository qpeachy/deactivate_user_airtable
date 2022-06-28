#!/usr/bin/env python3

# Purpose:
# Deactivate users
# users are loaded from a CSV file, that was generated from the Airtable Web UI

import logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)

from typing import List, Mapping, Optional, Tuple, Generator, Dict
import requests
import json
import csv
from os import environ
from sys import argv
from pathlib import Path

api_token = environ.get("AIRTABLE_API_TOKEN", None)
if not api_token:
  print("Please set your Airtable API token by typing 'export AIRTABLE_API_TOKEN=MYTOKEN'")
  exit(1)

account_id = environ.get("AIRABLE_ACCOUNT_ID", None)
if not account_id:
  print("Please set your Airtable enterprise account ID by typing 'export AIRABLE_ACCOUNT_ID=MYID'")
  exit(1)

headers = {"Authorization": f"Bearer {api_token}"}


class User():
  """
  Represents an Airtable base (database). Fields are loaded from a row in
  a CSV file export generated by Airtable.
  """
  def __init__(self, row: Mapping) -> None:
    self.id = row.get("User ID")
    self.first_name = row.get("User first name")
    self.last_name = row.get("User last name")
    self.email = row.get("User email")
    self.account_types = row.get("Account types")
    self.two_factor_auth = row.get("Two-factor auth enabled?")
    self.email_verified = row.get("Email verified?")
    self.invited_by_ID = row.get("Invited by ID")
    self.invited_by_email = row.get("Invited by email")
    self.last_active = row.get("Last active (UTC)")
    self.joined = row.get("Joined (UTC)")
    self.billable = row.get("Billable?")
    self.smic_external_ID = row.get("SCIM: External ID")
    self.smic_title = row.get("SCIM: Title")
    self.smic_cost_center = row.get("SCIM: Cost center")
    self.smic_department = row.get("SCIM: Department")
    self.smic_division = row.get("SCIM: Division")
    self.smic_organization = row.get("SCIM: Organization")
    self.smic_manager_display_name =row.get("SCIM: Manager display name")
    self.smic_manager =row.get("SCIM: Manager")

  def __repr__(self) -> str:
    return f"<{__class__.__name__}> {self.id}"


def deactivate_user(
  user: User,
  enterprise_account_id: str
) -> None:
  """
  Use Airtable API to move base from a workspace Id to another workspace Id.
  """
  url = "https://api.airtable.com/v0/meta/enterpriseAccounts/" \
      + enterprise_account_id + "/users/" + user.id
  body = {
    "state": "deactivated",
    "email": user.email,
    "firstName": user.first_name,
    "lastName": user.last_name
  }
  log.info(
    f"Deactivating user {user.first_name} {user.last_name}..."
  )

  try:
    response = requests.patch(url=url, data=body, headers=headers)
    status_code = response.status_code
    if status_code != 200:
      log.info(f"Status: {response.status_code}")

    try:
      json_response = response.json()
      if json_response:
        log.info(f"Got response: {json.dumps(json_response, indent=2)}")
    except:
        pass
    response.raise_for_status()
  except Exception as e:
    log.error(f"Error sending patch request {response.request}: {e}")
    raise


# Default to looking into the current working directory for now:
DEACTIVATED_USERS = Path() / "deactivated.txt"


def load_cached_processed() -> List[str]:
  """
  Load file on disk where previously migrated bases have been recorded.
  """
  # TODO ask user if they want to load or delete this file
  if DEACTIVATED_USERS.exists():
    print(f"{DEACTIVATED_USERS.name} exists, loading its base ids to avoid processing those again...")
    with open(DEACTIVATED_USERS, 'r') as f:
      return [line.rstrip() for line in f]
  return []


def yield_from_CSV(csv_file_path: Path, delimiter=',') -> Generator[Dict[str, str], None, None]:
  """
  Yield each line from a CSV file as a mapping of strings
  """
  with open(csv_file_path, 'r') as f:
    csv_reader = csv.DictReader(f, delimiter=delimiter)
    if not csv_reader:
      raise Exception(f"No data found in input file {csv_file_path.name}.")

    for row in csv_reader:
      yield row


def deactivate_user_from_csv(
  csv_path: Path
) -> None:
  """
  Read a CSV file (exported from Airtable's web UI) listing Aitable users,
  and depending on the mode, attempt to deactive each user
  Args:
    csv_path: Path. CSV file listing users to deactivate.
  """
  cached_processed = load_cached_processed()
  print(f"Loaded {len(cached_processed)} ids from cache that will not be processed.")

  deactivated_users = []
  failed = []

  for row in yield_from_CSV(csv_path):
    user = User(row)

    if user.id in cached_processed:
      # We have processed this one before and successfully deactivated it
      continue

    # A zero-length string seems to be valid still for these fields:
    if user.first_name is None or not isinstance(user.first_name, str):
      print(f"Missing or invalid first name attribute for {user}: {user.first_name}")
      failed.append(user)
      continue
    if user.email is None or not isinstance(user.email, str):
      print(f"Missing or invalid email attribute  for {user}: {user.email}")
      failed.append(user)
      continue
    if user.last_name is None or not isinstance(user.last_name, str):
      failed.append(user)
      print(f"Missing or invalid last name attribute for {user}: {user.last_name}")
      continue

    try:
      deactivate_user(
        user=user,
        enterprise_account_id=account_id,
      )
      deactivated_users.append(user.id)
    except Exception as e:
      print(f"Error during request for user deactivation of {user.id}: {e}")
      failed.append(user)
    else:
      with open(DEACTIVATED_USERS, 'a') as fp:
        fp.write(f"{user.id}\n")

  print(f"Sucessfully processed {len(deactivated_users)} entries from {csv_path.name}.")
  if failed:
    print(f"Failed to process {len(failed)} user id : {failed}.")


if __name__ == "__main__":
  if len(argv) < 2:
    print(f"Usage: python3 {__file__.split('/')[-1]} \"path/to/file.csv\"\n")
    exit(1)

  # First argument should be path to CSV file to read
  input_csv_file = Path(argv[1])
  if not input_csv_file.exists():
    print(f"Input file {input_csv_file.name} was not found.")
    exit(1)

  deactivate_user_from_csv(csv_path=input_csv_file)
