#!/usr/bin/python
# -*- coding: utf-8 -*-

try:
    from linode import api as linode_api
    HAS_LINODE = True
except ImportError as ie:
    HAS_LINODE = False
    LINODE_IMPORT_ERROR = str(ie)


DOCUMENTATION = '''
---
module: linode_nodebalancer
short_description: create / delete / update a Linode NodeBalancer
description:
  - Wrapper around the Linode NodeBalancer API https://www.linode.com/api/nodebalancer or https://www.linode.com/docs/platform/nodebalancer/nodebalancer-reference-guide
version_added: "1.9.4"
author: Duncan Morris (@duncanmorris)
requirements:
  - This module runs locally, not on the remote server(s)
  - It relies on the linode-python library https://github.com/tjfontaine/linode-python
options:
  api_key:
    required: false
    type: string
    description:
      - Your Linode API key, (see https://www.linode.com/docs/platform/api/api-key). You could pass it in directly to the module, or set it as an environment variable (LINODE_API_KEY).
  name:
    required: false
    type: string
    description:
      - The name of the NodeBalancer being targeted.
  node_balancer_id:
    required: false
    type: integer
    description:
      - The id of the NodeBalancer being targeted. This is not exposed anywhere obvious (other than the API), so typically you would target via name. One of name, or node_balancer_id is required. If present, this takes precedence over the name when looking up the NodeBalancer.
  state:
    required: false
    choices: ['present', 'absent']
    default: present
    type: string
    description:
      - The desired state of the NodeBalancer
  datacenter_id:
    required: false
    default: 7 (London)
    type: integer
    description:
      - The id of the Linode datacenter the NodeBalancer should be in. Must be an integer between 2 and 9. See Linode for the full list - https://www.linode.com/api/utility/avail.datacenters
  paymentterm:
    required: false
    type: integer
    default: 1
    choices: [1, 12, 24]
    description: The payment term for the NodeBalancer. One of 1, 12, or 24 months
  client_conn_throttle:
    required: false
    default: 0
    type: integer
    description:
      - Allowed connections per second, per client IP. 0 to disable.
'''

EXAMPLES = '''
- name: Ensure NodeBalancer Name is present
  local_action:
    module: linode_nodebalancer
    api_key: "{{ linode_api_key }}"
    name: "NodeBalancer Name"
    state: present
'''


def handle_api_error(func):
    """A decorator that catches any API errors from the Linode API and
    returns ansible module fail_json.

    An ansible module instance must be the first argument to the func
    """
    def handle(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except linode_api.ApiError as e:
            code = e.value[0]['ERRORCODE']
            err = e.value[0]['ERRORMESSAGE']
            msg = "FATAL: Code [{code}] - {err}".format(code=code,
                                                        err=err)
            return args[0].fail_json(msg=msg)
    return handle


@handle_api_error
def linodeNodeBalancers(module, api, state, name, node_balancer_id,
                        datacenter_id, paymentterm, client_conn_throttle):
    """ Ensure the given node balancer is in the correct state.

    If it is present and is meant to be, then potentially update it to
    ensure the other settings are up to date.

    If it is present and isn't meant to be, then delete it

    If it is absent but should be present, then create it, with the
    given settings.

    If it is correctly absent, then ignore
    """

    changed = False

    nodebalancer = linode_find_nodebalancer(api, node_balancer_id, name)
    if nodebalancer:
        if state == "present":
            if nodebalancer['LABEL'] != name or \
               nodebalancer['CLIENTCONNTHROTTLE'] != client_conn_throttle:
                update_kwargs = {}
                if nodebalancer['LABEL'] != name:
                    update_kwargs['Label'] = name
                new = api.nodebalancer_update(
                    NodeBalancerID=nodebalancer['NODEBALANCERID'],
                    ClientConnThrottle=client_conn_throttle,
                    **update_kwargs)
                changed = True
                nodebalancer = linode_find_nodebalancer(api,
                                                 new['NodeBalancerID'],
                                                 name)
        elif state == "absent":
            api.nodebalancer_delete(
                NodeBalancerId=nodebalancer['NODEBALANCERID']
            )
            nodebalancer = None
            changed = True

    else:
        if state == "present":
            new = api.nodebalancer_create(DatacenterID=datacenter_id,
                                    PaymentTerm=paymentterm,
                                    Label=name)
            nodebalancer = linode_find_nodebalancer(api,
                                             new['NodeBalancerID'],
                                             name)
            changed = True

        elif state == "absent":
            pass

    module.exit_json(changed=changed, instance=nodebalancer, instances=[nodebalancer])


# ===========================================
def main():
    module = AnsibleModule(
        argument_spec=dict(
            api_key=dict(required=False,
                         aliases=['linode_api_id'],
                         type='str'),
            name=dict(required=False,
                      type='str'),
            node_balancer_id=dict(required=False,
                                  type='int'),
            state=dict(required=False,
                       default='present',
                       choices=['present', 'absent'],
                       type='str'),
            datacenter_id=dict(required=False,
                               default=7,
                               type='int'),
            paymentterm=dict(required=False,
                             default=1,
                             choices=[1, 12, 24],
                             type='int'),
            client_conn_throttle=dict(required=False,
                                      default=0,
                                      type='int')
        ),
        required_one_of=[
            ['name', 'node_balancer_id']
        ],
        supports_check_mode=False
    )

    if not HAS_LINODE:
        module.fail_json(msg=LINODE_IMPORT_ERROR + " (pip install linode-python)")

    api_key = module.params.get('api_key')
    name = module.params.get('name')
    node_balancer_id = module.params.get('node_balancer_id')
    state = module.params.get('state')
    datacenter_id = module.params.get('datacenter_id')
    paymentterm = module.params.get('paymentterm')
    client_conn_throttle = module.params.get('client_conn_throttle')

    # Setup the api_key
    if not api_key:
        try:
            api_key = os.environ['LINODE_API_KEY']
        except KeyError, e:
            module.fail_json(msg='Unable to load %s' % e.message)

    # setup the auth
    try:
        api = linode_api.Api(api_key)
        api.test_echo()
    except Exception, e:
        module.fail_json(msg='%s' % e.value[0]['ERRORMESSAGE'])

    linodeNodeBalancers(module, api, state, name, node_balancer_id,
                        datacenter_id, paymentterm, client_conn_throttle)


from ansible.module_utils.basic import *
from ansible.module_utils.linode import *

if __name__ == '__main__':
    main()
