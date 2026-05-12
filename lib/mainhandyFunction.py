# for Logging
import time
from unittest import result
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from google_auth_oauthlib import flow
from googleapiclient.errors import HttpError

import io
import pickle

import logging
import warnings

# for data processing
# time processing
import datetime
from time import sleep
import pytz
import shutil

import json
from glob import glob
import requests
import pandas as pd
import openpyxl

# for path processing
import os

# for web url encode
import urllib.parse

import openpyxl.styles as styl

from .mainDecorator import decorator_catchError


def changeCl_df(mapping_df, in_df):
    sub_df = pd.DataFrame()
    for cl in mapping_df.columns.tolist():
        if cl == 'FLAG':
            if 'FLAG' in in_df.columns.tolist():
                sub_df['FLAG'] = in_df['FLAG']
        else:
            if mapping_df[cl][0] != '':
                if mapping_df[cl][0] in in_df.columns.tolist():

                    sub_df[cl] = in_df[mapping_df[cl][0]]
                else:
                    sub_df[cl] = ''
            else:
                sub_df[cl] = ''

    sub_df.fillna('')

    return sub_df


def readMapping(mediaType='Axis'):
    mainFolder_path = r'C:\Users\DT0083\Desktop\Python Learning\CostChecker\CostChecker'
    filePath = os.path.join(
        mainFolder_path, '00_setting', 'columnMapping_ver1.0.xlsx')

    mapping_df = pd.read_excel(
        filePath, sheet_name='Costchecker', header=0, engine='openpyxl')
    mapping_df = mapping_df.fillna('')
    mapping_df = mapping_df[mapping_df['FLAG']
                            == mediaType].reset_index(drop=True)

    mapping_df.fillna('')

    return mapping_df


def fommatExcelFile(filePath):
    # def style
    allCell_style = styl.NamedStyle(name="allCell_style")
    allCell_style.font = styl.Font(name="メイリオ", size=8)
    allCell_style.alignment = styl.Alignment(
        horizontal="left", vertical="center")

    # open file
    wb1 = openpyxl.load_workbook(filePath)
    for ws in wb1.worksheets:
        for row in ws:
            for cell in row:
                cell.style = allCell_style  # apply style to each cell

    # save wb
    wb1.save(filePath)
    wb1.close()


def makeDirs(inPathList):

    for path in inPathList:
        if not os.path.isdir(path):
            os.makedirs(path)
    logging.debug('Create folder: DONE')


class GDrive:
    def __init__(self, cridentialPath=os.getcwd(), cridentialFileName='client_secrets.json'):
        self.cridentialPath = cridentialPath
        self.cridentialFileName = cridentialFileName
        self.service = self.getService()

    def getService(self):
        creds = self.getCridential()
        service = build('drive', 'v3', credentials=creds,
                        cache_discovery=False)

        return service

    def getCridential(self):
        # If modifying these scopes, delete the file token.pickle.
        SCOPES = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive',
        ]

        """Shows basic usage of the Sheets API.
        Prints values from a sample spreadsheet.
        """
        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        basePath = self.cridentialPath
        if os.path.exists(os.path.join(basePath, 'token.pickle')):
            with open(os.path.join(basePath, 'token.pickle'), 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                appflow = flow.InstalledAppFlow.from_client_secrets_file(
                    os.path.join(basePath, self.cridentialFileName), SCOPES)
                creds = appflow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(os.path.join(basePath, 'token.pickle'), 'wb') as token:
                pickle.dump(creds, token)

        return creds

    def downloadFile(self, fileID):
        """Downloads a file
        Args:
            real_file_id: ID of the file to download
        Returns : IO object with location.
        Load pre-authorized user credentials from the environment.
        TODO(developer) - See https://developers.google.com/identity
        for guides on implementing OAuth2 for the application.
        """
        try:
            # pylint: disable=maybe-no-member
            request = self.service.files().get_media(fileId=fileID)
            file = io.BytesIO()
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                logging.debug(F'Download {int(status.progress() * 100)}.')

        except HttpError as error:
            logging.debug(F'An error occurred: {error}')
            file = None

        return file

    def getFileInfo(self, fileID):
        results = self.service.files().get(fileId=fileID).execute()
        return results

    def createFolder(self, folderName, parentID=None):
        # Create a folder on Drive, returns the newely created folders ID
        body = {
            'name': folderName,
            'mimeType': "application/vnd.google-apps.folder"
        }
        if parentID:
            body['parents'] = [parentID]
        root_folder = self.service.files().create(body=body).execute()

        return root_folder['id']

    def uploadFile(self, filePath, parentID=None):
        body = {
            'name': os.path.basename(filePath),
            'mimeType': '*/*'
        }
        if parentID:
            body['parents'] = [parentID]
        media = MediaFileUpload(filePath,
                                mimetype='*/*',
                                resumable=True)
        file = self.service.files().create(
            body=body, media_body=media, fields='id').execute()
        fileID = file.get('id')
        logging.debug(f"file upload done, fileID {fileID}")
        return fileID


class SpreadSheet:
    def __init__(self, cridentialPath=os.getcwd(), cridentialFileName='client_secrets.json'):
        self.cridentialPath = cridentialPath
        self.cridentialFileName = cridentialFileName
        self.class_initialize()

    def class_initialize(self):
        """update cridential, service, script service
        """
        cmd_list = [self.getCridential,
                    self.getService, self.getScriptsService]
        for cmd in cmd_list:
            cmd()

    def getScriptsService(self):
        service = build('script', 'v1', credentials=self.cridential,
                        cache_discovery=False)

        # Call the Sheets API
        # sheet = service.spreadsheets()
        self.scriptService = service

    def getService(self):
        service = build('sheets', 'v4', credentials=self.cridential,
                        cache_discovery=False)

        # Call the Sheets API
        # sheet = service.spreadsheets()
        self.service = service

    def getCridential(self, file_name: str = 'token.pickle') -> None:
        # If modifying these scopes, delete the file token.pickle.
        SCOPES = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive',
        ]

        """Shows basic usage of the Sheets API.
        Prints values from a sample spreadsheet.
        """
        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        basePath = self.cridentialPath
        if os.path.exists(os.path.join(basePath, file_name)):
            with open(os.path.join(basePath, file_name), 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                appflow = flow.InstalledAppFlow.from_client_secrets_file(
                    os.path.join(basePath, self.cridentialFileName), SCOPES)
                creds = appflow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(os.path.join(basePath, file_name), 'wb') as token:
                pickle.dump(creds, token)

        self.cridential = creds

    def runScript(self, appID, functionName, para=None):
        service = self.scriptService
        if para:
            request = {"function": functionName,
                       "parameters": para}
        else:
            request = {"function": functionName}
        try:
            result = service.scripts().run(body=request, scriptId=appID).execute()
            return result
        except HttpError as error:
            # The API encountered a problem.
            print(error.content)

    def create(self, title):
        service = self.service
        # [START sheets_create]
        spreadsheet = {
            'properties': {
                'title': title
            }
        }
        spreadsheet = service.spreadsheets().create(body=spreadsheet,
                                                    fields='spreadsheetId').execute()
        logging.debug('Spreadsheet ID: {0}'.format(
            spreadsheet.get('spreadsheetId')))
        # [END sheets_create]
        return spreadsheet.get('spreadsheetId')

    def clear(self, spreadsheet_id, clear_range):
        spreadsheet_id = spreadsheet_id
        range_ = clear_range
        clear_values_request_body = {
            # TODO: Add desired entries to the request body.
        }
        request = self.service.spreadsheets().values().clear(spreadsheetId=spreadsheet_id,
                                                             range=range_, body=clear_values_request_body)

        response = request.execute()
        return response

    def batch_update(self, spreadsheet_id, title, find, replacement):
        service = self.service
        # [START sheets_batch_update]
        requests = []
        # Change the spreadsheet's title.
        requests.append({
            'updateSpreadsheetProperties': {
                'properties': {
                    'title': title
                },
                'fields': 'title'
            }
        })
        # Find and replace text
        requests.append({
            'findReplace': {
                'find': find,
                'replacement': replacement,
                'allSheets': True
            }
        })
        # Add additional requests (operations) ...

        body = {
            'requests': requests
        }
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body).execute()
        find_replace_response = response.get('replies')[1].get('findReplace')
        logging.debug('{0} replacements made.'.format(
            find_replace_response.get('occurrencesChanged')))
        # [END sheets_batch_update]
        return response

    def get_values(self, spreadsheet_id, range_name):
        service = self.service
        # [START sheets_get_values]
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            majorDimension='ROWS').execute()
        rows = result.get('values', [])
        logging.debug('{0} rows retrieved.'.format(len(rows)))
        # [END sheets_get_values]
        return result

    def batch_get_values(self, spreadsheet_id, _range_names):
        service = self.service
        # [START sheets_batch_get_values]
        range_names = [
            # Range names ...
        ]
        # [START_EXCLUDE silent]
        range_names = _range_names
        # [END_EXCLUDE]
        result = service.spreadsheets().values().batchGet(
            spreadsheetId=spreadsheet_id, ranges=range_names).execute()
        ranges = result.get('valueRanges', [])
        logging.debug('{0} ranges retrieved.'.format(len(ranges)))
        # [END sheets_batch_get_values]
        return result

    def update_values(self, spreadsheet_id, range_name, value_input_option, _values):
        service = self.service
        # [START sheets_update_values]
        values = [
            [
                # Cell values ...
            ],
            # Additional rows ...
        ]
        # [START_EXCLUDE silent]
        values = _values
        # [END_EXCLUDE]
        body = {
            'values': values
        }
        result = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, range=range_name,
            valueInputOption=value_input_option, body=body).execute()
        logging.debug('{0} cells updated.'.format(result.get('updatedCells')))
        # [END sheets_update_values]
        return result

    def batch_update_values(self, spreadsheet_id, range_name,
                            value_input_option, _values):
        service = self.service
        # [START sheets_batch_update_values]
        values = [
            [
                # Cell values ...
            ],
            # Additional rows
        ]
        # [START_EXCLUDE silent]
        values = _values
        # [END_EXCLUDE]
        data = [
            {
                'range': range_name,
                'values': values
            },
            # Additional ranges to update ...
        ]
        body = {
            'valueInputOption': value_input_option,
            'data': data
        }
        result = service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id, body=body).execute()
        logging.debug('{0} cells updated.'.format(
            result.get('totalUpdatedCells')))
        # [END sheets_batch_update_values]
        return result

    def append_values(self, spreadsheet_id, range_name, value_input_option,
                      _values):
        service = self.service
        # [START sheets_append_values]
        values = [
            [
                # Cell values ...
            ],
            # Additional rows ...
        ]
        # [START_EXCLUDE silent]
        values = _values
        # [END_EXCLUDE]
        body = {
            'values': values
        }
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id, range=range_name,
            valueInputOption=value_input_option, body=body).execute()
        logging.debug('{0} cells appended.'.format(result
                                                   .get('updates')
                                                   .get('updatedCells')))

        # [END sheets_append_values]
        return result

    def pivot_tables(self, spreadsheet_id):
        service = self.service
        # Create two sheets for our pivot table.
        body = {
            'requests': [{
                'addSheet': {}
            }, {
                'addSheet': {}
            }]
        }
        batch_update_response = service.spreadsheets() \
            .batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
        source_sheet_id = batch_update_response.get('replies')[0] \
            .get('addSheet').get('properties').get('sheetId')
        target_sheet_id = batch_update_response.get('replies')[1] \
            .get('addSheet').get('properties').get('sheetId')
        requests = []
        # [START sheets_pivot_tables]
        requests.append({
            'updateCells': {
                'rows': {
                    'values': [
                        {
                            'pivotTable': {
                                'source': {
                                    'sheetId': source_sheet_id,
                                    'startRowIndex': 0,
                                    'startColumnIndex': 0,
                                    'endRowIndex': 20,
                                    'endColumnIndex': 7
                                },
                                'rows': [
                                    {
                                        'sourceColumnOffset': 1,
                                        'showTotals': True,
                                        'sortOrder': 'ASCENDING',

                                    },

                                ],
                                'columns': [
                                    {
                                        'sourceColumnOffset': 4,
                                        'sortOrder': 'ASCENDING',
                                        'showTotals': True,

                                    }
                                ],
                                'values': [
                                    {
                                        'summarizeFunction': 'COUNTA',
                                        'sourceColumnOffset': 4
                                    }
                                ],
                                'valueLayout': 'HORIZONTAL'
                            }
                        }
                    ]
                },
                'start': {
                    'sheetId': target_sheet_id,
                    'rowIndex': 0,
                    'columnIndex': 0
                },
                'fields': 'pivotTable'
            }
        })
        body = {
            'requests': requests
        }
        response = service.spreadsheets() \
            .batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
        # [END sheets_pivot_tables]
        return response

    def conditional_formatting(self, spreadsheet_id):
        service = self.service

        # [START sheets_conditional_formatting]
        my_range = {
            'sheetId': 0,
            'startRowIndex': 1,
            'endRowIndex': 11,
            'startColumnIndex': 0,
            'endColumnIndex': 4,
        }
        requests = [{
            'addConditionalFormatRule': {
                'rule': {
                    'ranges': [my_range],
                    'booleanRule': {
                        'condition': {
                            'type': 'CUSTOM_FORMULA',
                            'values': [{
                                'userEnteredValue':
                                    '=GT($D2,median($D$2:$D$11))'
                            }]
                        },
                        'format': {
                            'textFormat': {
                                'foregroundColor': {'red': 0.8}
                            }
                        }
                    }
                },
                'index': 0
            }
        }, {
            'addConditionalFormatRule': {
                'rule': {
                    'ranges': [my_range],
                    'booleanRule': {
                        'condition': {
                            'type': 'CUSTOM_FORMULA',
                            'values': [{
                                'userEnteredValue':
                                    '=LT($D2,median($D$2:$D$11))'
                            }]
                        },
                        'format': {
                            'backgroundColor': {
                                'red': 1,
                                'green': 0.4,
                                'blue': 0.4
                            }
                        }
                    }
                },
                'index': 0
            }
        }]
        body = {
            'requests': requests
        }
        response = service.spreadsheets() \
            .batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
        logging.debug('{0} cells updated.'.format(
            len(response.get('replies'))))
        # [END sheets_conditional_formatting]
        return response

    def filter_views(self, spreadsheet_id):
        service = self.service

        # [START sheets_filter_views]
        my_range = {
            'sheetId': 0,
            'startRowIndex': 0,
            'startColumnIndex': 0,
        }
        addFilterViewRequest = {
            'addFilterView': {
                'filter': {
                    'title': 'Sample Filter',
                    'range': my_range,
                    'sortSpecs': [{
                        'dimensionIndex': 3,
                        'sortOrder': 'DESCENDING'
                    }],
                    'criteria': {
                        0: {
                            'hiddenValues': ['Panel']
                        },
                        6: {
                            'condition': {
                                'type': 'DATE_BEFORE',
                                'values': {
                                    'userEnteredValue': '4/30/2016'
                                }
                            }
                        }
                    }
                }
            }
        }

        body = {'requests': [addFilterViewRequest]}
        addFilterViewResponse = service.spreadsheets() \
            .batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()

        duplicateFilterViewRequest = {
            'duplicateFilterView': {
                'filterId':
                addFilterViewResponse['replies'][0]['addFilterView']['filter']
                ['filterViewId']
            }
        }

        body = {'requests': [duplicateFilterViewRequest]}
        duplicateFilterViewResponse = service.spreadsheets() \
            .batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()

        updateFilterViewRequest = {
            'updateFilterView': {
                'filter': {
                    'filterViewId': duplicateFilterViewResponse['replies'][0]
                    ['duplicateFilterView']['filter']['filterViewId'],
                    'title': 'Updated Filter',
                    'criteria': {
                        0: {},
                        3: {
                            'condition': {
                                'type': 'NUMBER_GREATER',
                                'values': {
                                    'userEnteredValue': '5'
                                }
                            }
                        }
                    }
                },
                'fields': {
                    'paths': ['criteria', 'title']
                }
            }
        }

        body = {'requests': [updateFilterViewRequest]}
        updateFilterViewResponse = service.spreadsheets() \
            .batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
        logging.debug(str(updateFilterViewResponse))
        # [END sheets_filter_views]


class Chatwork_client():
    def __init__(self, api_key: str = '66d7468c0232a7a8d0c24d8ef8c2a71c') -> None:
        self._api_key = api_key

    @decorator_catchError('2001: msg to CW error')
    def sendMessage(self, room_id, text_message_as_string):
        APIKEY = self._api_key
        ENDPOINT = 'https://api.chatwork.com/v2'
        room_id = room_id
        bodytext = text_message_as_string
        post_message_url = '{}/rooms/{}/messages'.format(ENDPOINT, room_id)

        headers = {'X-ChatWorkToken': APIKEY}
        # print(str(bodytext))
        params = {'body': str(bodytext)}

        resp = requests.post(post_message_url,
                             headers=headers,
                             params=params)

        return resp.content.decode('utf-8')

    @decorator_catchError('2002: file to CW error')
    def sendFile(self, room_id, file_name, file_path):
        APIKEY = self._api_key
        ENDPOINT = 'https://api.chatwork.com/v2'
        room_id = room_id
        file_path = file_path
        file_name = file_name
        if file_name != 'default':
            file_name = file_name
        else:
            # print(file_path)
            file_name = file_path[file_path.rfind('\\')+1:]

        post_message_url = '{}/rooms/{}/files'.format(ENDPOINT, room_id)

        headers = {'X-ChatWorkToken': APIKEY}

        files = {'file': (file_name, open(file_path, 'rb'),
                          'application/vnd.ms-excel')}

        resp = requests.post(post_message_url, headers=headers, files=files)
        return resp.content.decode('utf-8')


def clearFileInDirs(inPathList):
    for delFolder in inPathList:
        for filename in os.listdir(delFolder):
            file_path = os.path.join(delFolder, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                logging.debug('Failed to delete %s. Reason: %s' %
                              (file_path, e))