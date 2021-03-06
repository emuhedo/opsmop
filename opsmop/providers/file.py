# Copyright 2018 Michael DeHaan LLC, <michael@michaeldehaan.net>
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import shutil
from pathlib import Path

from opsmop.core.errors import ProviderError
from opsmop.facts.filetests import FileTests
from opsmop.core.template import Template
from opsmop.providers.provider import Provider

class File(Provider):

    # ---------------------------------------------------------------  
   
    def should_replace_using_template(self):
        """ for from_template , should we write the template? """
        if not FileTests.exists(self.name):
            return True
        if not self.overwrite:
            return False
        self.evaluated_template = Template.from_file(self.from_template, self.resource)
        c1 = FileTests.string_checksum(self.evaluated_template)
        c2 = FileTests.checksum(self.name)
        return c1 != c2
    
    # ---------------------------------------------------------------

    def should_replace_using_content(self):
        """ for from_content, should we write the file? """
        if not FileTests.exists(self.name):
            return True
        if not self.overwrite:
            return False
        c1 = FileTests.string_checksum(self.from_content)
        c2 = FileTests.checksum(self.name)
        return c1 != c2

    # ---------------------------------------------------------------

    def should_replace_using_file(self):
        """ for from_file, should we write the file? """
        if not FileTests.exists(self.name):
            return True
        if not self.overwrite:
            return False
        return not FileTests.same_contents(self.name, self.from_file)

    # ---------------------------------------------------------------

    def plan(self):
        """ what actions are needed? """

        exists = FileTests.exists(self.name)

        if FileTests.is_directory(self.name):
            raise ProviderError(self, f"Is a directory: {self.name}")

        # removal?
        if self.absent:
            if not exists:
                self.needs("rm")
            return

        # content?
        if (self.from_content or self.from_template or self.from_file):
            if self.from_template:
                if self.should_replace_using_template():
                    self.needs('copy_template')
            elif self.from_file:
                if self.should_replace_using_file():
                    self.needs('copy_file')
            elif self.from_content:
                if self.should_replace_using_content():
                    self.needs('copy_content')

        # metadata?
        if self.owner and (not exists or not (FileTests.owner(self.name) == self.owner)):
            self.needs('chown')
        if self.group and (not exists or not (FileTests.group(self.name) == self.group)):
            self.needs('chgrp')
        if self.mode and (not exists or not (FileTests.mode(self.name) == self.mode)):
            self.needs('chmod')

    # ---------------------------------------------------------------

    def apply(self):
        """
        Apply homebrew status changes.
        """

        # TODO: from_url would be a great feature to have
        
        # removal ...

        if self.should('rm'):
            self.do('rm')
            self.path.unlink()
            return self.ok()
        
        # creation ...

        elif self.should('copy_file'):
            self.do('copy_file')
            shutil.copy2(self.from_file, self.name)

        elif self.should('copy_template'):
            self.do('copy_template')
            data = open(self.name, "w")  
            data.write(self.evaluated_template)
            data.close()

        elif self.should('copy_content'):
            self.do('copy_content')
            data = open(self.name, "w")
            data.write(self.from_content)
            data.close()

        # metadata ...
        
        if self.should('chmod'):
            self.do('chmod')
            os.chmod(self.name, self.mode)

        if self.should('chown'):
            self.do('chown')
            try:
                shutil.chown(self.name, user=self.owner)
            except PermissionError:
                return self.fatal("chown failed")

        if self.should('chgrp'):
            self.do('chgrp')
            try:
                shutil.chown(self.name, group=self.group)
            except PermissionError:
                return self.fatal("chgrp failed")

        return self.ok()
