from utils.cv_parser import CVParser
import json

profile = CVParser.mock_parse("test_cv.pdf")
print(json.dumps(profile, indent=2))
