@echo off
REM Python script for model and metadata preparation
python prepare_models.py

REM Nuitka build execution
python -m nuitka ^
    --standalone ^
    --follow-imports ^
    --include-package=fastapi ^
    --include-package=uvicorn ^
    --include-package=langchain ^
    --include-package=langchain_community ^
    --include-package=langchain_community.document_loaders ^
    --include-package=langchain_core ^
    --include-package=faiss ^
    --include-package=numpy ^
    --include-package=cv2 ^
    --include-package=easyocr ^
    --include-package=sentence_transformers ^
    --include-package=pydantic ^
    --include-package=pptx ^
    --include-package=PIL ^
    --include-package=torch ^
    --include-package=tokenizers ^
    --include-package=tqdm ^
    --include-package=yaml ^
    --include-package=packaging ^
    --include-package=filelock ^
    --include-package=regex ^
    --include-package=requests ^
    --include-package=charset_normalizer ^
    --include-package=certifi ^
    --include-package=idna ^
    --include-package=urllib3 ^
    --include-package=typing_extensions ^
    --include-package=starlette ^
    --include-package=anyio ^
    --include-package=click ^
    --include-package=h11 ^
    --include-package=kiwipiepy ^
    --include-package=kiwipiepy_model ^
    --include-package=transformers ^
    --include-package=transformers.models ^
    --include-package=zstandard ^
    --include-package=langsmith ^
    --nofollow-import-to=transformers.testing_utils ^
    --nofollow-import-to=transformers.models.dinov2_with_registers ^
    --include-module=sentence_transformers ^
    --include-distribution-metadata=torchaudio ^
    --include-distribution-metadata=torch ^
    --include-distribution-metadata=transformers ^
    --include-distribution-metadata=sentence_transformers ^
    --windows-icon-from-ico=private_devbot.ico ^
    --output-dir=build ^
    main.py

REM Copy necessary model files after build
echo Copying necessary model files...

REM Copy Kiwipiepy model files - FIXED PATH
echo Copying Kiwipiepy model files...
if not exist "build\main.dist\kiwipiepy_model" mkdir "build\main.dist\kiwipiepy_model"
for /F "tokens=*" %%G in ('python -c "import kiwipiepy_model; import os; print(os.path.dirname(kiwipiepy_model.__file__))"') do (
    set KIWIPIEPY_PATH=%%G
)
xcopy /E /I /Y "%KIWIPIEPY_PATH%\*" "build\main.dist\kiwipiepy_model\"

REM Copy embedding model files (if they exist)
echo Copying embedding model files...
if exist "embedding_model" (
    if not exist "build\main.dist\embedding_model" mkdir "build\main.dist\embedding_model"
    xcopy /E /I /Y "embedding_model\*" "build\main.dist\embedding_model\"
)

REM Copy EasyOCR model files (if they exist)
echo Copying EasyOCR model files...
if exist "easyocr_model" (
    if not exist "build\main.dist\easyocr_model" mkdir "build\main.dist\easyocr_model"
    xcopy /E /I /Y "easyocr_model\*" "build\main.dist\easyocr_model\"
)

REM Copy other necessary files (config files, etc.)
echo Copying config files...
if exist "config.yaml" copy /Y "config.yaml" "build\main.dist\"
if exist "allowed_ips.json" copy /Y "allowed_ips.json" "build\main.dist\"
if exist "devbot_config.yaml" copy /Y "devbot_config.yaml" "build\main.dist\"

echo Build complete! Executable file has been created in the build\main.dist folder.
