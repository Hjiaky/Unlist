# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""An upload handler that streams an mbox upload straight into the data directory.

Django's default handlers keep small uploads in memory and large ones in the system temp
directory. A Takeout export can be many gigabytes, and mail belongs nowhere but the data
directory, so the upload view writes every file there instead. The file is removed when
the request ends; `importer.store_upload` keeps its own link to it for the scan.
"""

import tempfile

from django.core.files.uploadedfile import UploadedFile
from django.core.files.uploadhandler import FileUploadHandler

from unlist.mail import importer


class DataDirUploadedFile(UploadedFile):
    def __init__(self, name, content_type, size, charset, content_type_extra=None):
        directory = importer.import_dir()
        directory.mkdir(parents=True, exist_ok=True)
        file = tempfile.NamedTemporaryFile(suffix=".upload", dir=directory)  # deleted on close
        super().__init__(file, name, content_type, size, charset, content_type_extra)

    def temporary_file_path(self):
        return self.file.name

    def close(self):
        try:
            return self.file.close()
        except FileNotFoundError:
            pass


class DataDirUploadHandler(FileUploadHandler):
    def new_file(self, *args, **kwargs):
        super().new_file(*args, **kwargs)
        self.file = DataDirUploadedFile(self.file_name, self.content_type, 0, self.charset, self.content_type_extra)

    def receive_data_chunk(self, raw_data, start):
        self.file.write(raw_data)

    def file_complete(self, file_size):
        self.file.seek(0)
        self.file.size = file_size
        return self.file
