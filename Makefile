# will break if multiple .py files exist
exe :
	rm -rf *.exe _internal
	pyinstaller *.py
	mv dist/*/* .
	rm -rf dist *.spec

clean :
	rm -rf *.exe _internal build dist *.spec
