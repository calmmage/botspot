Logic is as follows:

1) do NOT import any modules to botspot.components/__init__.py
2) import all useful utils in botspot.utils/__init__.py
3) import all useful components in botspot/__init__.py
4) import all useful utils in botspot/__init__.py
5) for components that have multiple functions, create a new service file under botspot/
   and import all the relevant classes and functions there
    - example: botspot/user_data.py
6) Bonus: for components with getter util functions add this function to a file with
   component and expose via __all__ 