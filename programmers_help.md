# Help for programmers

## Starting virt env from scratch
- conda create --name viQCd
- conda activate viQCd
- cd C:\....\imageQC_dash
- pip install -e .

using virt env later
- conda activate viQCd
- cd C:\...\imageQC_dash
- python -m imageQC_dash.imageQC_dash # to run the program

## Update requirements.txt
Add manually to requirements.txt + setup.cfg or:
- cd to src-folder
- pipreqs 
- requirements will now be in the src-folder. Move it to folder above src.
- remove plotly/dash_core_components/dash_html_components (already included with dash)
- Copy also new content to setup.cfg

## Update pdf version of Wiki
- download wikidoc code from https://github.com/jobisoft/wikidoc
	- Replace wikidoc.py in wikidoc-master with the one in helper_scripts folder where the code is updated for python3 and some fixes for linking pages
- install exe files: 
	- pandoc https://pandoc.org/installing.html 
	- wkhtmltopdf https://wkhtmltopdf.org

- conda install -c anaconda git
Clone git from github
- git clone https://github.com/EllenWasbo/imageQC_dash.wiki.git &lt;some path&gt;\imageQCpy_wiki
- or update with Pull and GitHub Desktop

- cd to wikidoc-master
- python wikidoc.py C:\Programfiler\wkhtmltopdf\bin\wkhtmltopdf.exe &lt;some path&gt;\\imageQC_dash_wiki\

Note that code used by wikidoc are within the .md files of imageQCpy/wiki

## For building .exe
Unlike imageQC, imageQC_dash have failed building the packages correctly with pyinstaller. Thus cx_Freeze is used instead of pyinstaller.

- Install python (v3.11-3.13 and choose to add path to be able to run python from cmd (not via Anaconda)
- Create an empty folder called e.g. cx_Freeze
- Create an empty folder withing your cx_Freeze folder called imageQC_dash
- Copy into the empty imageQC_dash folder src and all files directly from folder above src except .gitignore/.pylintrc

In cmd.exe (not from Anaconda)
- cd to the cx_Freeze folder
- python -m venv iQCd (creates a new virtual environment in the current folder, if you already have one, make sure it is deactivated and delete the venv folder)
- iQCd\Scripts\activate.bat
- pip install cx_freeze
- cd to the folder above src
- pip install -e .
- delete setup.py, pyproject.toml, setup.cfg from cx_Freeze/imageQC_dash
- in cx_Freeze/imageQC_dash/src/imageQC_dash/imageQC_dash.py (line ~ 234) switch assets_folder definition
	- &#35; assets_folder = str(Path(__file__).parent / 'assets')
    - assets_folder = str(Path(os.getcwd()) / 'assets')  # when exe
- cd imageQC_dash
- python setup_cx_freeze.py build
- wait 5 min
- test imageQC_dash.exe file in build when finished
	- cd to the folder above the file
	- imageQC_dash
- zip content of folder build to distribute imageQC_dash.zip
