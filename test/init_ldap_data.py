"""
此脚本使用一些测试数据初始化 LDAP 服务器。

它创建了两个组织单元（技术部和市场部）以及两个用户（张三和李四），每个部门一个用户。此脚本旨在手动运行，用于设置 LDAP 服务器以进行测试。

Author: Guo Lijian
"""
# 需要安装 ldap3: pip install ldap3
from ldap3 import Server, Connection, ALL

# 配置必须和 docker-compose 一致
LDAP_SERVER = "ldap://localhost:389"
LDAP_USER = "cn=admin,dc=mycompany,dc=com"
LDAP_PASSWORD = "admin"
BASE_DN = "dc=mycompany,dc=com"

def init_ldap():
    try:
        # 连接 LDAP
        server = Server(LDAP_SERVER, get_info=ALL)
        conn = Connection(server, user=LDAP_USER, password=LDAP_PASSWORD, auto_bind=True)
        print("✅ LDAP 连接成功")

        # 1. 创建两个部门 (OU - Organizational Unit)
        # 研发部
        tech_dn = f"ou=研发部,{BASE_DN}"
        conn.add(tech_dn, attributes={
            'objectClass': ['top', 'organizationalUnit'],
            'ou': '研发部'
        })
        print(f"创建部门: 研发部 -> {conn.result['description']}")

        # 市场部
        market_dn = f"ou=人力资源部,{BASE_DN}"
        conn.add(market_dn, attributes={
            'objectClass': ['top', 'organizationalUnit'],
            'ou': '人力资源部'
        })
        print(f"创建部门: 人力资源部 -> {conn.result['description']}")

        # 2. 创建用户 (inetOrgPerson)
        # 用户 1: zhangsan (属于 Tech)
        zhang_dn = f"uid=zhangsan,ou=研发部,{BASE_DN}"
        conn.add(zhang_dn, attributes={
            'objectClass': ['top', 'person', 'organizationalPerson', 'inetOrgPerson'],
            'cn': 'Zhang San',
            'sn': 'Zhang',
            'uid': 'zhangsan',
            'mail': 'zhangsan@mycompany.com',
            'userPassword': 'password123'  # 密码
        })
        print(f"创建用户: zhangsan -> {conn.result['description']}")

        # 用户 2: lisi (属于 Marketing)
        li_dn = f"uid=lisi,ou=人力资源部,{BASE_DN}"
        conn.add(li_dn, attributes={
            'objectClass': ['top', 'person', 'organizationalPerson', 'inetOrgPerson'],
            'cn': 'Li Si',
            'sn': 'Li',
            'uid': 'lisi',
            'mail': 'lisi@mycompany.com',
            'userPassword': 'password123'
        })
        print(f"创建用户: lisi -> {conn.result['description']}")

        conn.unbind()
        print("\n🎉 LDAP 测试数据初始化完成！")

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print("如果提示 'Entry already exists' 说明之前已经运行过，可以忽略。")

if __name__ == "__main__":
    init_ldap()