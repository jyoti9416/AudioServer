import os

from pymongo import MongoClient
from flask import Flask, request
from flask_restful import Api, Resource
from audio import Song,Podcast, Audiobook
from audio import MetadataValueError, MetadataGenerationError

client = MongoClient(os.environ.get('AUDIO_SERVER'))
collection = client['AudioServer']['audiofiles']


def generate_400_response(error):
    return {'status': 400, 'message': 'Bad Request', 'error': error}


def generate_500_response(error):
    return {'status': 500, 'message': 'Internal Server Error', 'error': error}


app = Flask(__name__)
api = Api(app)

def new_audio(audiotype: str, audiometadata: dict):
    """ A function that generates an Audio object, one of Song, Podcast and Audiobook
    and returns it. Returns None if the 'audiotype' is invalid. """
    try:
        audiotype = audiotype.lower()

        if audiotype == "song":
            file = Song(audiometadata)
        elif audiotype == "podcast":
            file = Podcast(audiometadata)
        elif audiotype == "audiobook":
            file = Audiobook(audiometadata)
        else:
            return None

        return file

    except MetadataValueError as error:
        raise MetadataValueError(error)

    except MetadataGenerationError as error:
        raise MetadataGenerationError(error)



class Create(Resource):
    def post(self):
        data = request.get_json()

        try:
            audiotype:str = data['audioFileType']
            audiometadata:dict = data['audioFileMetadata']

        except KeyError as key:
            response = generate_400_response(f"{key} is required")
            return response,400

        if not isinstance(audiotype):
            response = generate_400_response("'audioFileType' must be an string")
            return response,400

        if not isinstance(audiometadata):
            response = generate_400_response("'audioFileMetadata' must be an dict")
            return response,400

        try:
            audiotype = audiotype.capitalize()
            audiofile = new_audio(audiotype,audiometadata)

            if not audiofile:
                response = generate_400_response(f"'{audiofile}' is not supported")
                return response,400

        except MetadataValueError as error:
            response = generate_400_response(f"{error}")
            return response, 400

        except MetadataGenerationError as error:
            response = generate_500_response(f"metadata generation for {audiotype} - {error}")
            return response, 500

        insert_result = collection.insert_one(audiofile.metadata)

        if not insert_result.acknowledged:
            response = generate_500_response("database insertion failed")
            return response, 500

        return {"status":200,"message":"Creation Completed","result":f"{audiotype} file with ID {insert_result.inserted_id} has been created",
                "document":insert_result.inserted_id},200

class Delete(Resource):
    """ Resource for deleting audio files from the server """
    def get(self,audiotype:str,audioID:int):
        audiotype = audiotype.capitalize()

        if audiotype.lower() not in ['song','podcast','audiobook']:
            response = generate_400_response(f"'{audiotype}' is not supported")
            return response,400

        try:
            search_fil = {'type':audiotype,'_id':audioID}
            delete_res = collection.find_one_and_delete(search_fil)

        except Exception as error:
            response = generate_500_response(f"database query and delete failed - {error}")
            return response,500

        if not delete_res:
            return {'status': 200, 'message': 'Delete Completed','result':f"No document deleted"},200

        return {'status': 200, 'message': 'Delete Completed','result':f"{audiotype} file with ID {delete_res['_id']}",
                'document':delete_res['_id']},200

class Update(Resource):
    """ Resource for updating audio files on the server """
    def post(self,audiotype:str, audioID:int):
        audiotype = audiotype.capitalize()

        if audiotype.lower() not in ['song','podcast','audiobook']:
            response = generate_400_response(f"'{audiotype}' is not supported")
            return response,400

        data = request.get_json()

        try:
            audiotyp_param: str = data['audioFileType']
            audiometadata:dict = data['audioFileMetadata']

        except KeyError as key:
            response = generate_400_response()(f"{key} is required")
            return response, 400

        if not isinstance(audiotyp_param, str):
            response = generate_400_response("'audioFileType' must be an str")
            return response, 400

        if not isinstance(audiometadata, dict):
            response = generate_400_response("'audioFileMetadata' must be a dict")
            return response, 400

        if audiotyp_param.capitalize() != audiotype:
            response = generate_400_response("'audioFileType' must match endpoint")
            return response, 400

        try:
            search_filter = {'type':audiotype,'_id':audioID}
            old_doc = collection.find_one(search_filter)

        except Exception as error:
            response = generate_500_response(f"database query failed - {error}")
            return response, 500

        if not old_doc:
            response = generate_400_response(f"No document found for ID - {audioID}")
            return response, 400

        try:
            new_audiofile = new_audio(audiotype, audiometadata)

            if not new_audiofile:
                response = generate_400_response(f"'{audiotype}' is not supported")
                return response, 400

            new_document = new_audiofile.metadata
            new_document['_id'] = old_doc['_id']

        except MetadataValueError as error:
            response = generate_400_response(f"{error}")
            return response, 400

        except MetadataGenerationError as error:
            response = generate_500_response(f"metadata generation for {audiotype} - {error}")
            return response, 500

        except Exception as error:
            response = generate_500_response(f"document update failed - {error}")
            return response, 500

        try:
            pre_update_doc = collection.find_one_and_replace(search_filter, new_document)

        except Exception as error:
            response = generate_500_response(f"database query and replace failed - {error}")
            return response, 500

        return {
            "status": 200,
            "message": "Update Complete",
            "result": f"{audiotype} file with ID {audioID} has been updated",
            "pre-update": pre_update_doc,
            "post-update": new_document,
            "document": audioID
        }, 200

class Get(Resource):
    """ Resource for retrieving audio files from the server """
    def get(self, audiotype: str, audioID: int = None):
        """ RESTful GET Method. """
        audiotype = audiotype.capitalize()

        if audiotype.lower() not in ['song', 'podcast', 'audiobook']:
            response = generate_400_response(f"'{audiotype}' is not supported")
            return response, 400

        try:
            if audioID:
                search = {"type": audiotype, "_id": audioID}
                result = collection.find_one(search)
                result = [result] if result else []
            else:
                search = {"type": audiotype}
                search_result = collection.find(search)
                result = [res for res in search_result]

        except Exception as error:
            response = generate_500_response(f"database query failed - {error}")
            return response, 500

        return {
            "status": 200,
            "message": "Get Complete",
            "result": f"{len(result)} result(s) found",
            "documents": result,
            "matches": len(result)
        }, 200

api.add_resource(Create, '/create')
api.add_resource(Delete, '/delete/<string:audiotype>/<int:audioID>')
api.add_resource(Update, '/update/<string:audiotype>/<int:audioID>')
api.add_resource(Get, '/get/<string:audiotype>', '/get/<string:audiotype>/<int:audioID>')

if __name__ == '__main__':
    app.run()













