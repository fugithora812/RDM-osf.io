import unittest
from nose.tools import *  # PEP8 asserts

from tests.base import OsfTestCase
from tests.test_features import requires_search
from tests.factories import (
    UserFactory, ProjectFactory, NodeFactory,
    UnregUserFactory, UnconfirmedUserFactory
)

from framework.auth.core import Auth

#Uncomment to force elasticsearch to load for testing
# if settings.SEARCH_ENGINE is not None:
#    settings.SEARCH_ENGINE = 'elastic'
import website.search.search as search


@requires_search
class SearchTestCase(OsfTestCase):

    def set_up(self):
        """Common setup operations to all tests"""
        search.delete_all()
        search.create_index()

    def tearDown(self):
        super(SearchTestCase, self).tearDown()
        search.delete_all()


def query(term, tags=''):
    full_result = search.search({'query': term, 'type': '', 'tags': tags})
    return full_result['results']


def query_user(name):
    full_result = search.search({'query': name, 'type': 'user', 'tags': ''})
    return full_result['results']


@requires_search
class TestUserUpdate(SearchTestCase):

    def setUp(self):
        super(TestUserUpdate, self).setUp()
        self.set_up()
        self.user = UserFactory(fullname='David Bowie')

    def test_new_user(self):
        # Verify that user has been added to Elastic Search
        docs = query_user(self.user.fullname)
        assert_equal(len(docs), 1)

    def test_new_user_unconfirmed(self):
        user = UnconfirmedUserFactory()
        docs = query_user(user.fullname)
        assert_equal(len(docs), 0)
        token = user.get_confirmation_token(user.username)
        user.confirm_email(token)
        user.save()
        docs = query_user(user.fullname)
        assert_equal(len(docs), 1)

    def test_change_name(self):
        """Add a user, change her name, and verify that only the new name is
        found in search.

        """
        user = UserFactory(fullname='Barry Mitchell')
        fullname_original = user.fullname
        user.fullname = user.fullname[::-1]
        user.save()

        docs_original = query_user(fullname_original)
        assert_equal(len(docs_original), 0)

        docs_current = query_user(user.fullname)
        assert_equal(len(docs_current), 1)

    def test_merged_user(self):
        user = UserFactory(fullname='Annie Lennox')
        merged_user = UserFactory(fullname='Lisa Stansfield')
        user.save()
        merged_user.save()
        assert_equal(len(query_user(user.fullname)), 1)
        assert_equal(len(query_user(merged_user.fullname)), 1)

        user.merge_user(merged_user)

        assert_equal(len(query_user(user.fullname)), 1)
        assert_equal(len(query_user(merged_user.fullname)), 0)

    def test_employment(self):
        user = UserFactory(fullname='Helga Finn')
        user.save()
        institution = 'Finn\'s Fine Filers'

        docs = query('user:' + institution)
        assert_equal(len(docs), 0)
        user.jobs.append({
            'institution': institution,
            'title': 'The Big Finn',
        })
        user.save()

        docs = query('user:' + institution)
        assert_equal(len(docs), 1)

    def test_education(self):
        user = UserFactory(fullname='Henry Johnson')
        user.save()
        institution = 'Henry\'s Amazing School!!!'

        docs = query('user:' + institution)
        assert_equal(len(docs), 0)
        user.schools.append({
            'institution': institution,
            'degree': 'failed all classes',
        })
        user.save()

        docs = query('user:' + institution)
        assert_equal(len(docs), 1)


@requires_search
class TestProject(SearchTestCase):

    def setUp(self):
        super(TestProject, self).setUp()
        self.set_up()
        self.user = UserFactory(fullname='John Deacon')
        self.project = ProjectFactory(title='Red Special', creator=self.user)

    def test_new_project_private(self):
        """Verify that a private project is not present in Elastic Search.
        """
        docs = query(self.project.title)
        assert_equal(len(docs), 0)

    def test_make_public(self):
        """Make project public, and verify that it is present in Elastic
        Search.
        """
        self.project.set_privacy('public')
        docs = query(self.project.title)
        assert_equal(len(docs), 1)


@requires_search
class TestPublicNodes(SearchTestCase):

    def setUp(self):
        super(TestPublicNodes, self).setUp()
        self.set_up()
        self.user = UserFactory(usename='Doug Bogie')
        self.title = 'Red Special'
        self.consolidate_auth = Auth(user=self.user)
        self.project = ProjectFactory(
            title=self.title,
            creator=self.user,
            is_public=True
        )
        self.component = NodeFactory(
            project=self.project,
            title=self.title,
            creator=self.user,
            is_public=True
        )
        self.registration = ProjectFactory(
            title=self.title,
            creator=self.user,
            is_public=True,
            is_registration=True
        )

    def test_make_private(self):
        """Make project public, then private, and verify that it is not present
        in search.
        """
        self.project.set_privacy('private')
        docs = query('project:' + self.title)
        assert_equal(len(docs), 0)

        self.component.set_privacy('private')
        docs = query('component:' + self.title)
        assert_equal(len(docs), 0)

        self.registration.set_privacy('private')
        docs = query('registration:' + self.title)
        assert_equal(len(docs), 0)

    def test_make_parent_private(self):
        """Make parent of component, public, then private, and verify that the
        component still appears but doesn't link to the parent in search.
        """
        self.project.set_privacy('private')
        docs = query('component:' + self.title)
        assert_equal(len(docs), 1)
        assert_equal(docs[0]['parent_title'], '-- private project --')
        assert_false(docs[0]['parent_url'])

    def test_delete_project(self):
        """

        """
        self.component.remove_node(self.consolidate_auth)
        docs = query('component:' + self.title)
        assert_equal(len(docs), 0)

        self.project.remove_node(self.consolidate_auth)
        docs = query('project:' + self.title)
        assert_equal(len(docs), 0)

    def test_change_title(self):
        """

        """
        title_original = self.project.title
        self.project.set_title(
            'Blue Ordinary', self.consolidate_auth, save=True)

        docs = query('project:' + title_original)
        assert_equal(len(docs), 0)

        docs = query('project:' + self.project.title)
        assert_equal(len(docs), 1)

    def test_add_tags(self):

        tags = ['stonecoldcrazy', 'just a poor boy', 'from-a-poor-family']

        for tag in tags:
            docs = query('', tags=tag)
            assert_equal(len(docs), 0)
            self.project.add_tag(tag, self.consolidate_auth, save=True)

        for tag in tags:
            docs = query('', tags=tag)
            assert_equal(len(docs), 1)

    def test_remove_tag(self):

        tags = ['stonecoldcrazy', 'just a poor boy', 'from-a-poor-family']

        for tag in tags:
            self.project.add_tag(tag, self.consolidate_auth, save=True)
            self.project.remove_tag(tag, self.consolidate_auth, save=True)
            docs = query('', tags=tag)
            assert_equal(len(docs), 0)

    def test_update_wiki(self):
        """Add text to a wiki page, then verify that project is found when
        searching for wiki text.

        """
        wiki_content = 'Hammer to fall'

        docs = query(wiki_content)
        assert_equal(len(docs), 0)

        self.project.update_node_wiki(
            'home', wiki_content, self.consolidate_auth,
        )

        docs = query(wiki_content)
        assert_equal(len(docs), 1)

    def test_clear_wiki(self):
        """Add wiki text to page, then delete, then verify that project is not
        found when searching for wiki text.

        """
        wiki_content = 'Hammer to fall'
        self.project.update_node_wiki(
            'home', wiki_content, self.consolidate_auth,
        )
        self.project.update_node_wiki('home', '', self.consolidate_auth)

        docs = query(wiki_content)
        assert_equal(len(docs), 0)

    def test_add_contributor(self):
        """Add a contributor, then verify that project is found when searching
        for contributor.

        """
        user2 = UserFactory(fullname='Adam Lambert')

        docs = query('project:"{}"'.format(user2.fullname))
        assert_equal(len(docs), 0)

        self.project.add_contributor(user2, save=True)

        docs = query('project:"{}"'.format(user2.fullname))
        assert_equal(len(docs), 1)

    def test_remove_contributor(self):
        """Add and remove a contributor, then verify that project is not found
        when searching for contributor.

        """
        user2 = UserFactory(fullname='Brian May')

        self.project.add_contributor(user2, save=True)
        self.project.remove_contributor(user2, self.consolidate_auth)

        docs = query('project:"{}"'.format(user2.fullname))
        assert_equal(len(docs), 0)

    def test_hide_contributor(self):
        user2 = UserFactory(fullname='Brian May')
        self.project.add_contributor(user2)
        self.project.set_visible(user2, False, save=True)
        docs = query('project:"{}"'.format(user2.fullname))
        assert_equal(len(docs), 0)
        self.project.set_visible(user2, True, save=True)
        docs = query('project:"{}"'.format(user2.fullname))
        assert_equal(len(docs), 1)

    def test_word_cloud(self):
        tag1 = 'general tag'
        tag2 = 'specific tag'
        self.project.add_tag(tag1, self.consolidate_auth, save=True)
        self.component.add_tag(tag1, self.consolidate_auth, save=True)
        self.component.add_tag(tag2, self.consolidate_auth, save=True)

        # can't use "query" function because I need the word cloud, not results
        res = search.search({'query': self.title, 'type': '', 'tags': ''})
        cloud = res['cloud']

        assert_equal(len(cloud), 2)
        assert_equal(cloud[0], (tag1, 2))
        assert_equal(cloud[1], (tag2, 1))

    def test_wrong_order_search(self):
        title_parts = self.title.split(' ')
        title_parts.reverse()
        title_search = ' '.join(title_parts)

        docs = query(title_search)
        assert_equal(len(docs), 3)


@requires_search
class TestAddContributor(SearchTestCase):
    """Tests of the search.search_contributor method

    """

    def setUp(self):
        super(TestAddContributor, self).setUp()
        self.set_up()
        self.name1 = 'Roger1 Taylor1'
        self.name2 = 'John2 Deacon2'
        self.user = UserFactory(fullname=self.name1)

    def test_unreg_users_dont_show_in_search(self):
        unreg = UnregUserFactory()
        contribs = search.search_contributor(unreg.fullname)
        assert_equal(len(contribs['users']), 0)

    def test_search_fullname(self):
        """Verify that searching for full name yields exactly one result.

        """
        contribs = search.search_contributor(self.name1)
        assert_equal(len(contribs['users']), 1)

        contribs = search.search_contributor(self.name2)
        assert_equal(len(contribs['users']), 0)

    def test_search_firstname(self):
        """Verify that searching for first name yields exactly one result.

        """
        contribs = search.search_contributor(self.name1.split(' ')[0])
        assert_equal(len(contribs['users']), 1)

        contribs = search.search_contributor(self.name2.split(' ')[0])
        assert_equal(len(contribs['users']), 0)

    def test_search_partial(self):
        """Verify that searching for part of first name yields exactly one
        result.

        """
        contribs = search.search_contributor(self.name1.split(' ')[0][:-1])
        assert_equal(len(contribs['users']), 1)

        contribs = search.search_contributor(self.name2.split(' ')[0][:-1])
        assert_equal(len(contribs['users']), 0)
