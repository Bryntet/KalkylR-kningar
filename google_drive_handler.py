from __future__ import print_function

import os
import json
import copy
from pyairtable import Base


from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive']


def make_creds():
    """Shows basic usage of the Drive v3 API.
    Prints the names and ids of the first 10 files the user has access to.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token_drive.json'):
        creds = Credentials.from_authorized_user_file('token_drive.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token_drive.json', 'w') as token:
            token.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)


def search_file(service):

    try:
        # create drive api client
        files = []
        page_token = None
        i = 0
        while True:
            # pylint: disable=maybe-no-member
            response = service.files().list(
                q="mimeType='image/jpeg'",
                spaces='drive',
                fields='nextPageToken, '
                'files(id, name)',
                pageToken=page_token
            ).execute()
            for file in response.get('files', []):
                # Process change
                print(F'Found file: {file.get("name")}, {file.get("id")}')
            files.extend(response.get('files', []))
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
            i += 1
            if i == 100:
                i = 0
                print(files)
    except HttpError as error:
        print(F'An error occurred: {error}')
        files = None

    return files


def create_folder(service, name, parent_id=None) -> str:

    try:

        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            file_metadata['parents'] = [parent_id]

        # pylint: disable=maybe-no-member
        file = service.files().create(body=file_metadata,
                                      fields='id').execute()

        return file.get('id')

    except HttpError as error:
        print(F'An error occurred: {error}')
        return None


api_key = os.environ["api_key"]
base_id = os.environ["base_id"]

service = make_creds()
airtable_base = Base(api_key, base_id)
top_parent = os.environ['DRIVE_TOP_FOLDER']


projekt_table = airtable_base.get_table('Projekt')
our_clients = airtable_base.get_table('Kund')
end_clients = airtable_base.get_table('Slutkund')


# DRID = Drive ID
# RID = Record ID


class Kund:
    def __init__(self, service, top_parent: str, name: str, rid: str, year, DRID=None, sub_DRIDs=None):
        self.service = service
        self.top_parent = top_parent
        self.KUND_NAME = name
        self.year = year
        self.KUND_RID = rid

        if DRID is not None:
            self.KUND_DRID: str = DRID
        else:
            self.KUND_DRID = self.make_folder(name)


        if sub_DRIDs is not None: # If we have subfolders
            self.sub_DRIDs: dict[str, dict] = sub_DRIDs
            if year not in self.sub_DRIDs.keys():
                self.sub_DRIDs[year] = {'drid': self.make_folder(year, self.KUND_DRID)}
        
        else: #Make subfolder for year
            self.sub_DRIDs = {year: {'drid': self.make_folder(year, self.KUND_DRID)}}
        self.lowest_DRID = self.sub_DRIDs[year]['drid']
        
    def make_if_drid_not_none(self, name, parent_id, drid) -> str:
        if drid is not None:
            self.lowest_DRID = drid
            return drid
        else:
            return self.make_folder(name, parent_id)


    def get_link(self) -> str:
        return f"https://drive.google.com/drive/folders/{self.lowest_DRID}"


    def make_folder(self, name, parent_id=None) -> str:
        if not parent_id:
            parent_id = self.top_parent
            print('No parent id, using top parent')
        else:
            print(parent_id)
            
        new_folder = create_folder(self.service, name, parent_id)
        self.lowest_DRID = copy.deepcopy(new_folder)
        return new_folder

    def get_dict(self) -> dict:
        return {
            self.KUND_RID: {
                'drid': self.KUND_DRID,
                self.year: self.sub_DRIDs[self.year]
            }
        }



class Slutkund(Kund):
    def __init__(self, service, kund_top_parent: str, kund_name: str, kund_rid: str, year: str, slutkund: str, slutkund_rid: str, projekt: str, projekt_rid: str, slutkund_drid=None, leverans_drid=None, kund_DRID=None, kund_sub_DRIDs=None):
        super().__init__(service, kund_top_parent, kund_name, kund_rid, year, kund_DRID, kund_sub_DRIDs)

        self.slutkund_name = slutkund
        self.projekt_name = projekt
        self.slutkund_rid = slutkund_rid
        self.projekt_rid = projekt_rid

        self.slutkund_drid = super().make_if_drid_not_none(self.slutkund_name, self.sub_DRIDs[year]['drid'], slutkund_drid)
        self.projekt_drid = super().make_if_drid_not_none(self.projekt_name, self.slutkund_drid, leverans_drid)

        self.sub_DRIDs[self.year].update({
            slutkund_rid: {
                'drid': self.slutkund_drid,
                self.projekt_rid: self.projekt_drid
            }
        })


def main():
    if os.path.exists('drive_struct.json'):
        with open('drive_struct.json', 'r', encoding='utf-8') as f:
            big_dict_with_all = json.load(f)
    else:
        big_dict_with_all = {}


    all_projekt = projekt_table.all()
    for projekt in all_projekt:
        the_len = len(all_projekt)
        print(f"{all_projekt.index(projekt)+1}/{the_len} {all_projekt.index(projekt)/the_len*100}%")
        big_dict_with_all = all_the_processes(big_dict_with_all, projekt)
    
    with open('drive_struct.json', 'w', encoding='utf-8') as f:
        json.dump(big_dict_with_all, f, indent=4, ensure_ascii=False)

def all_the_processes(big_dict_with_all, projekt) -> dict:
    p_fields = projekt['fields']
    p_keys = p_fields.keys()
    if all([x in p_keys for x in ['Kund', 'År']]):
        year = p_fields['År']
        if type(year) is not dict:
            kund = our_clients.get(p_fields['Kund'][0])
            kund_name = kund['fields']['Kund'].lower()
            kund_rid = kund['id']
            kund_drid = None
            sublist = None
            slutkund_drid = None
            projekt_drid = None
            if kund_rid in big_dict_with_all.keys():
                kund_drid = big_dict_with_all[kund_rid]['drid']
                sublist = copy.deepcopy(big_dict_with_all)[kund_rid]
                sublist.pop('drid', None)
            next_thing = True
            if 'Slutkund' in p_keys:
                if our_clients.get(p_fields['Kund'][0])['fields']['Kund'].lower() != end_clients.get(p_fields['Slutkund'][0])['fields']['Name'].lower():
                    next_thing = False
                    slutkund = end_clients.get(p_fields['Slutkund'][0])
                    slutkund_name = slutkund['fields']['Name'].lower()
                    slutkund_rid = slutkund['id']


                    if kund_rid in big_dict_with_all.keys():
                        if year in big_dict_with_all[kund_rid].keys():
                            if slutkund_rid in big_dict_with_all[kund_rid][year].keys():
                                slutkund_drid = big_dict_with_all[kund_rid][year][slutkund_rid]['drid']
                                if projekt['id'] in big_dict_with_all[kund_rid][year][slutkund_rid].keys():
                                    projekt_drid = big_dict_with_all[kund_rid][year][slutkund_rid][projekt['id']]
                                    return big_dict_with_all
                    x = Slutkund(service, top_parent, kund_name, kund_rid, year, slutkund_name, slutkund_rid, p_fields['Name'].lower(), projekt['id'], slutkund_drid, projekt_drid, kund_drid, sublist)
                    make_proj_rid = False
            if next_thing:
                x = Kund(service, top_parent, kund_name, kund_rid, year, kund_drid, sublist)
                make_proj_rid = True
            url = x.get_link()
            projekt_table.update(projekt['id'], {'Kopplad drive': url})
            big_dict_with_all.update(x.get_dict())
            if make_proj_rid:
                made = x.make_folder(p_fields['Name'].lower(), big_dict_with_all[kund_rid][year]['drid'])
                big_dict_with_all[kund_rid][year].update({projekt['id']: made})
    return big_dict_with_all


def save(the_dict):
    with open('drive_struct.json', 'w', encoding='utf-8') as f:
        json.dump(the_dict, f, indent=4, ensure_ascii=False)

def load():
    with open('drive_struct.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def do_one(record_id):
    the_dict = load()
    save(all_the_processes(the_dict, projekt_table.get(record_id)[0]))

    
    
if __name__ == '__main__':
    main()