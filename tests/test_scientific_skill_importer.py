from installer.scientific_skill_importer import _infer_permissions, _map_agents


def test_map_agents_routes_research_skills_to_research_agent():
    agents = _map_agents("database-lookup", "Search public scientific databases")
    assert "research_agent" in agents


def test_map_agents_routes_writer_skills_to_writer_agent():
    agents = _map_agents("scientific-writing", "Write scientific reports and papers")
    assert "writer_agent" in agents


def test_map_agents_routes_bio_skills_to_bio_code_agent():
    agents = _map_agents("scanpy", "Single-cell RNA-seq bioinformatics workflows")
    assert "bio_code_agent" in agents


def test_map_agents_routes_integrations_to_executor_agent():
    agents = _map_agents("benchling-integration", "Cloud platform workflow integration")
    assert "executor_agent" in agents


def test_infer_permissions_uses_tools_and_description():
    perms = _infer_permissions(
        "database-lookup",
        ["Read", "Bash"],
        "Search APIs and download scientific database results",
    )
    assert perms["network"] is True
    assert perms["filesystem"] is False
    assert perms["shell"] is False
