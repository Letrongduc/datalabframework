import os
from datetime import datetime
import pytz

from datalabframework import logging
from datalabframework.yaml import yaml
from datalabframework._utils import merge

import json
import jsonschema

from dotenv import load_dotenv
from jinja2 import Environment

# metadata files are cached once read the first time
def read(file_paths=None):
    """
    Return all profiles, stored in a nested dictionary
    profiles are merged over the list provided profiles. list order determines override
    each profile name
    :param file_paths: list of yaml files
    :return: dict of profiles
    """
    profiles = {}

    if not file_paths:
        file_paths = []
    
    for filename in file_paths:
        if os.path.isfile(filename):
            with open(filename, 'r') as f:
                try:
                    docs = list(yaml.load_all(f))
                except yaml.YAMLError as e:
                    if hasattr(e, 'problem_mark'):
                        mark = e.problem_mark
                        logging.error("Error loading yml file {} at position: (%s:%s): skipping file".format(filename, mark.line+1, mark.column+1))
                        docs = []
                finally:
                    for doc in docs:
                        doc['profile'] = doc.get('profile', 'default')
                        profiles[doc['profile']] = merge(profiles.get(doc['profile'],{}), doc)

    return profiles

def inherit(profiles):
    """
    Modify profiles to inherit from default profile
    :param profiles: input dict of profiles
    :return: profile
    """

    # inherit from default for all other profiles
    for k in profiles.get('default', {}).keys():
        for p in profiles.keys() - 'default':
            profiles[p][k] = merge(profiles['default'][k], profiles[p].get(k))

    return profiles

def render(metadata, dotenv_path=None, max_passes=5):
    """
    Renders jinja expressions in the given input metadata.
    jinja templates can refer to the dictionary itself for variable substitution

    :param metadata: dict, input metadata with values containing jinja templates
    :param dotenv_path: file to export as env variables
    :param max_passes: max number of rendering passes
    :return: dict, rendered dictionary
    """

    # get env variables from .env file
    if dotenv_path and os.path.isfile(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)

    env = Environment()
    env.globals['env'] = lambda key, value=None: os.getenv(key, value)
    env.globals['now'] = lambda tz=None, format='%Y-%m-%d %H:%M:%S': datetime.strftime(datetime.now(pytz.timezone(tz if tz else 'UTC')), format)
    
    doc = json.dumps(metadata)

    rendered = metadata

    for i in range(max_passes):
        dictionary = json.loads(doc)

        #rendering with jinja
        template = env.from_string(doc)
        doc = template.render(dictionary)

        # all done, or more rendering required?
        rendered = json.loads(doc)
        if dictionary == rendered:
            break

    return rendered

def v(d, schema):
    message=None
    try:
        jsonschema.validate(d, schema)
        return
    except jsonschema.exceptions.ValidationError as e:
        message  = f'{e.message} \n\n## schema path:\n\'{"/".join(e.schema_path)}\'\n\n'
        message += f'## metadata schema definition {"for " + str(e.parent) if e.parent else ""}:'
        message += f'\n{yaml.dump(e.schema)}'
    
    if message:
        raise ValueError(message)
        
def validate_schema(md, schema_filename):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    filename = os.path.abspath(os.path.join(dir_path, 'schemas/{}'.format(schema_filename)))
    with open(filename) as f:
        v(md, yaml.load(f))

def validate(md):

    # validate data structure
    validate_schema(md, 'top.yml')
        
    # _validate_schema(md['loggers'], 'loggers.yml')

    # for d in md['providers']:
    #     _validate_schema(d, 'provider.yml')
    #
    # for d in md['resources']:
    #     _validate_schema(d, 'resource.yml')

    # validate semantics
    providers = md.get('providers', {}).keys()
    for resource_alias, r in md.get('resources',{}).items():
        resource_provider = r.get('provider')
        if resource_provider and resource_provider not in providers:
            print(
                f'resource {resource_alias}: given provider "{resource_provider}" does not match any metadata provider')

def load(profile=None, file_paths=None, dotenv_path=None, factory_defaults=True):
    """
    Load the profile, given a list of yml files and a .env filename
    profiles inherit from the defaul profile, a profile not found will contain the same elements as the default profile

    :param profile:
    :param file_paths:
    :param dotenv_path:
    :return:
    """
    if profile is None:
        profile = 'default'

    if factory_defaults:
        # get the default metadata configuration file
        dir_path = os.path.dirname(os.path.realpath(__file__))
        default_metadata_file = os.path.abspath(os.path.join(dir_path, 'schemas/default.yml'))
    
        #prepend the default configuration
        file_paths = [default_metadata_file] + file_paths

    profiles = read(file_paths)

    # empty profile if profile not found
    if profile not in profiles.keys():
        if file_paths:
            message = '\nList of loaded metadata files:\n'
            for f in file_paths:
                message += f'  - {f}\n'
            message += '\nList of available profiles:\n'
            for p in profiles.keys():
                message += f'  - {p}\n'   
        raise ValueError(f'Profile "{profile}" not found.\n{message}')

    # read metadata, get the profile, if not found get an empty profile
    profiles = inherit(profiles)
    metadata = profiles[profile]

    # render any jinja templates in the profile
    md = render(metadata, dotenv_path)
    
    # validate
    validate(md)
    
    return md
