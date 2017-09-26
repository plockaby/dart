import os
from flask import url_for, request


def init_app(app):
    @app.context_processor
    def override_url_for():
        return dict(url_for=dated_url_for)

    def dated_url_for(endpoint, **values):
        # if we're in debug mode then just return the file
        if (app.debug):
            return url_for(endpoint, **values)

        if (endpoint == "static" or endpoint.endswith(".static")):
            file_name = values.get("filename", None)
            if (file_name):
                # if there is no request then there are no caches to bust
                if (request):
                    # if the endpoint starts with a dot then we want to use the
                    # same blueprint as the current request. otherwise, we want
                    # to find blueprints that start the same as our endpoint
                    blueprint_name = None
                    if (endpoint.startswith(".")):
                        blueprint_name = request.blueprint
                    else:
                        # sort the longest first so that we match most specifically
                        for name in sorted(app.blueprints, key=lambda x: len(x)):
                            if (endpoint.startswith(name)):
                                blueprint_name = name
                                break  # found the blueprint, stop searching

                    # use the global static path unless we have a blueprint in
                    # which case we will use the blueprint's static path.
                    static_path = app.static_folder
                    if (blueprint_name):
                        blueprint = app.blueprints.get(blueprint_name)
                        static_path = blueprint.static_folder

                    # sometimes we might not have a static path globally or for
                    # a blueprint. if we don't then we can't get a timestamp.
                    if (static_path):
                        file_path = os.path.join(static_path, file_name)
                        if (os.path.isfile(file_path)):
                            values["q"] = int(os.stat(file_path).st_mtime)

        return url_for(endpoint, **values)
