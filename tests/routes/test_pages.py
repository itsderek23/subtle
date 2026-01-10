class TestSessionsList:
    def test_returns_200(self, client, session_factory):
        with session_factory.patch_projects_dir():
            response = client.get("/")

        assert response.status_code == 200
