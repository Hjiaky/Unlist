# Unlist

A self-hosted alternative to commercial personal-data removal services: one household runs it to discover which organizations hold its members' personal data, get that data removed, and keep it removed.

## Language

**Operator**:
The person who installs and runs an Unlist instance and acts on behalf of its **Subjects**. One per instance.
_Avoid_: User, admin, account

**Subject**:
A person whose personal data the **Operator** wants removed. An instance holds one or more.
_Avoid_: Profile, identity, member, client

**Organization**:
Any company or body that may hold a **Subject**'s personal data, such as a shop, app, newsletter sender or **Broker**. In GDPR terms, a controller.
_Avoid_: Service, company, controller, vendor

**Broker**:
An **Organization** whose business is collecting personal data and selling, renting or publishing it, including people-search sites.
_Avoid_: Data broker site, source

**Organization List**:
A shareable file describing **Organizations** (privacy contacts, whether each is a **Broker**, request quirks), published at a URL. An instance subscribes to several and adds its own local overrides, like adblocker filter lists.
_Avoid_: Directory, database, registry, blocklist

**Listing**:
An **Organization**'s record of a particular **Subject**. In the EU/UK a **Listing** is revealed by the **Organization**'s answer to an **Access Request**.
_Avoid_: Profile, entry, hit, match

**Access Request**:
A demand, sent to an **Organization** on behalf of a **Subject**, that it disclose whether it holds a **Listing** for that **Subject** and what it contains. In the EU/UK this is a GDPR Art. 15 request; a **Removal Request** follows only where a **Listing** exists.
_Avoid_: Lookup, search, DSAR, subject access request

**Removal Request**:
A demand, sent to an **Organization** on behalf of a **Subject**, that it delete that **Subject**'s data and stop processing it. In the EU/UK this is a GDPR Art. 17 erasure request.
_Avoid_: Opt-out, deletion request, takedown

**Supervisory Authority**:
The data-protection regulator an **Organization** answers to, such as a national data-protection authority in the EU or the UK regulator.
_Avoid_: DPA, regulator, data protection office

**Complaint**:
A submission to a **Supervisory Authority** about an **Organization** that failed to answer an **Access Request** or **Removal Request** properly or on time.
_Avoid_: Escalation, report
