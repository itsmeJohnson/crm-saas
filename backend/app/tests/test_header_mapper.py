from app.services.import_.header_mapper import calculate_confidence, suggest_mappings

def test_calculate_confidence_exact():
    assert calculate_confidence("last_name", "last_name") == 100
    assert calculate_confidence("Last Name", "last_name") == 100
    assert calculate_confidence("last-name", "last_name") == 100

def test_calculate_confidence_alias():
    assert calculate_confidence("lname", "last_name") == 80
    assert calculate_confidence("fname", "first_name") == 80
    assert calculate_confidence("owner_email", "assigned_email") == 80

def test_calculate_confidence_fuzzy():
    assert calculate_confidence("assign email", "assigned_email") == 60
    assert calculate_confidence("first namee", "first_name") == 60

def test_calculate_confidence_no_match():
    assert calculate_confidence("random_column", "email") == 0

def test_suggest_mappings():
    headers = ["First Name", "lname", "Email Address", "assign email", "UnrecognizedCol"]
    suggestions = suggest_mappings(headers)
    
    assert suggestions["first_name"]["column"] == "First Name"
    assert suggestions["first_name"]["confidence"] == 100
    
    assert suggestions["last_name"]["column"] == "lname"
    assert suggestions["last_name"]["confidence"] == 80
    
    assert suggestions["email"]["column"] == "Email Address"
    assert suggestions["email"]["confidence"] == 80
    
    assert suggestions["assigned_email"]["column"] == "assign email"
    assert suggestions["assigned_email"]["confidence"] == 60
