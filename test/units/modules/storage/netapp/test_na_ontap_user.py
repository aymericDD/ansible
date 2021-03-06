# (c) 2018, NetApp, Inc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

''' unit tests ONTAP Ansible module: na_ontap_user '''

from __future__ import print_function
import json
import pytest

from units.compat import unittest
from units.compat.mock import patch
from ansible.module_utils import basic
from ansible.module_utils._text import to_bytes
import ansible.module_utils.netapp as netapp_utils

from ansible.modules.storage.netapp.na_ontap_user \
    import NetAppOntapUser as my_module  # module under test

if not netapp_utils.has_netapp_lib():
    pytestmark = pytest.mark.skip('skipping as missing required netapp_lib')


def set_module_args(args):
    """prepare arguments so that they will be picked up during module creation"""
    args = json.dumps({'ANSIBLE_MODULE_ARGS': args})
    basic._ANSIBLE_ARGS = to_bytes(args)  # pylint: disable=protected-access


class AnsibleExitJson(Exception):
    """Exception class to be raised by module.exit_json and caught by the test case"""
    pass


class AnsibleFailJson(Exception):
    """Exception class to be raised by module.fail_json and caught by the test case"""
    pass


def exit_json(*args, **kwargs):  # pylint: disable=unused-argument
    """function to patch over exit_json; package return data into an exception"""
    if 'changed' not in kwargs:
        kwargs['changed'] = False
    raise AnsibleExitJson(kwargs)


def fail_json(*args, **kwargs):  # pylint: disable=unused-argument
    """function to patch over fail_json; package return data into an exception"""
    kwargs['failed'] = True
    raise AnsibleFailJson(kwargs)


class MockONTAPConnection(object):
    ''' mock server connection to ONTAP host '''

    def __init__(self, kind=None, parm1=None):
        ''' save arguments '''
        self.type = kind
        self.parm1 = parm1
        self.xml_in = None
        self.xml_out = None

    def invoke_successfully(self, xml, enable_tunneling):  # pylint: disable=unused-argument
        ''' mock invoke_successfully returning xml data '''
        self.xml_in = xml
        if self.type == 'user':
            xml = self.build_user_info(self.parm1)
        self.xml_out = xml
        return xml

    @staticmethod
    def set_vserver(vserver):
        '''mock set vserver'''
        pass

    @staticmethod
    def build_user_info(locked):
        ''' build xml data for user-info '''
        xml = netapp_utils.zapi.NaElement('xml')
        data = {'num-records': 1,
                'attributes-list': {'security-login-account-info': {'is-locked': locked}}}

        xml.translate_struct(data)
        print(xml.to_string())
        return xml


class TestMyModule(unittest.TestCase):
    ''' a group of related Unit Tests '''

    def setUp(self):
        self.mock_module_helper = patch.multiple(basic.AnsibleModule,
                                                 exit_json=exit_json,
                                                 fail_json=fail_json)
        self.mock_module_helper.start()
        self.addCleanup(self.mock_module_helper.stop)
        self.server = MockONTAPConnection()
        self.use_vsim = False

    def set_default_args(self):
        if self.use_vsim:
            hostname = '10.193.77.154'
            username = 'admin'
            password = 'netapp1!'
            user_name = 'test'
            vserver = 'ansible_test'
            application = 'console'
            authentication_method = 'password'
        else:
            hostname = 'hostname'
            username = 'username'
            password = 'password'
            user_name = 'name'
            vserver = 'vserver'
            application = 'console'
            authentication_method = 'password'

        return dict({
            'hostname': hostname,
            'username': username,
            'password': password,
            'name': user_name,
            'vserver': vserver,
            'applications': application,
            'authentication_method': authentication_method
        })

    def test_module_fail_when_required_args_missing(self):
        ''' required arguments are reported as errors '''
        with pytest.raises(AnsibleFailJson) as exc:
            set_module_args({})
            my_module()
        print('Info: %s' % exc.value.args[0]['msg'])

    def test_ensure_user_get_called(self):
        ''' a more interesting test '''
        module_args = {}
        module_args.update(self.set_default_args())
        module_args.update({'role_name': 'test'})
        set_module_args(module_args)
        my_obj = my_module()
        my_obj.server = self.server
        user_info = my_obj.get_user()
        print('Info: test_user_get: %s' % repr(user_info))
        assert user_info is None

    def test_ensure_user_apply_called(self):
        ''' creating user and checking idempotency '''
        module_args = {}
        module_args.update(self.set_default_args())
        module_args.update({'name': 'create'})
        module_args.update({'role_name': 'test'})
        set_module_args(module_args)
        my_obj = my_module()
        if not self.use_vsim:
            my_obj.server = self.server
        with pytest.raises(AnsibleExitJson) as exc:
            my_obj.apply()
        print('Info: test_user_apply: %s' % repr(exc.value))
        assert exc.value.args[0]['changed']
        if not self.use_vsim:
            my_obj.server = MockONTAPConnection('user', 'false')
        with pytest.raises(AnsibleExitJson) as exc:
            my_obj.apply()
        print('Info: test_user_apply: %s' % repr(exc.value))
        assert exc.value.args[0]['changed']

    def test_ensure_user_apply_for_delete_called(self):
        ''' deleting user and checking idempotency '''
        module_args = {}
        module_args.update(self.set_default_args())
        module_args.update({'name': 'create'})
        module_args.update({'role_name': 'test'})
        set_module_args(module_args)
        my_obj = my_module()
        if not self.use_vsim:
            my_obj.server = MockONTAPConnection('user', 'false')
        with pytest.raises(AnsibleExitJson) as exc:
            my_obj.apply()
        print('Info: test_user_apply: %s' % repr(exc.value))
        assert not exc.value.args[0]['changed']
        module_args.update({'state': 'absent'})
        set_module_args(module_args)
        my_obj = my_module()
        if not self.use_vsim:
            my_obj.server = MockONTAPConnection('user', 'false')
        with pytest.raises(AnsibleExitJson) as exc:
            my_obj.apply()
        print('Info: test_user_delete: %s' % repr(exc.value))
        assert exc.value.args[0]['changed']

    def test_ensure_user_lock_called(self):
        ''' changing user_lock to True and checking idempotency'''
        module_args = {}
        module_args.update(self.set_default_args())
        module_args.update({'name': 'create'})
        module_args.update({'role_name': 'test'})
        module_args.update({'lock_user': 'false'})
        set_module_args(module_args)
        my_obj = my_module()
        if not self.use_vsim:
            my_obj.server = MockONTAPConnection('user', 'false')
        with pytest.raises(AnsibleExitJson) as exc:
            my_obj.apply()
        print('Info: test_user_apply: %s' % repr(exc.value))
        assert not exc.value.args[0]['changed']
        module_args.update({'lock_user': 'true'})
        set_module_args(module_args)
        my_obj = my_module()
        if not self.use_vsim:
            my_obj.server = MockONTAPConnection('user', 'false')
        with pytest.raises(AnsibleExitJson) as exc:
            my_obj.apply()
        print('Info: test_user_lock: %s' % repr(exc.value))
        assert exc.value.args[0]['changed']

    def test_ensure_user_unlock_called(self):
        ''' changing user_lock to False and checking idempotency'''
        module_args = {}
        module_args.update(self.set_default_args())
        module_args.update({'name': 'create'})
        module_args.update({'role_name': 'test'})
        module_args.update({'lock_user': 'true'})
        set_module_args(module_args)
        my_obj = my_module()
        if not self.use_vsim:
            my_obj.server = MockONTAPConnection('user', 'true')
        with pytest.raises(AnsibleExitJson) as exc:
            my_obj.apply()
        print('Info: test_user_apply: %s' % repr(exc.value))
        assert not exc.value.args[0]['changed']
        module_args.update({'lock_user': 'false'})
        set_module_args(module_args)
        my_obj = my_module()
        if not self.use_vsim:
            my_obj.server = MockONTAPConnection('user', 'true')
        with pytest.raises(AnsibleExitJson) as exc:
            my_obj.apply()
        print('Info: test_user_unlock: %s' % repr(exc.value))
        assert exc.value.args[0]['changed']

    def test_ensure_user_set_password_called(self):
        ''' set password '''
        module_args = {}
        module_args.update(self.set_default_args())
        module_args.update({'name': 'create'})
        module_args.update({'role_name': 'test'})
        module_args.update({'set_password': '123456'})
        set_module_args(module_args)
        my_obj = my_module()
        if not self.use_vsim:
            my_obj.server = MockONTAPConnection('user', 'true')
        with pytest.raises(AnsibleExitJson) as exc:
            my_obj.apply()
        print('Info: test_user_apply: %s' % repr(exc.value))
        assert exc.value.args[0]['changed']
