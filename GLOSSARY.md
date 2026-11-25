# Unlist

A self-hosted alternative to commercial personal-data removal services: one household runs it to get its members' personal data removed from data brokers and keep it removed.

## Language

**Operator**:
The person who installs and runs an Unlist instance and acts on behalf of its **Subjects**. One per instance.
_Avoid_: User, admin, account

**Subject**:
A person whose personal data the **Operator** wants removed. An instance holds one or more.
_Avoid_: Profile, identity, member, client

**Broker**:
An organization that collects personal data and sells, rents or publishes it, including people-search sites.
_Avoid_: Data broker site, vendor, source

**Listing**:
A **Broker**'s record of a particular **Subject**. In the EU/UK a **Listing** is revealed by the **Broker**'s answer to an **Access Request**.
_Avoid_: Profile, entry, hit, match

**Access Request**:
A demand, sent to a **Broker** on behalf of a **Subject**, that it disclose whether it holds a **Listing** for that **Subject** and what it contains. In the EU/UK this is a GDPR Art. 15 request; a **Removal Request** follows only where a **Listing** exists.
_Avoid_: Lookup, search, DSAR, subject access request

**Removal Request**:
A demand, sent to a **Broker** on behalf of a **Subject**, that it delete that **Subject**'s data and stop processing it. In the EU/UK this is a GDPR Art. 17 erasure request.
_Avoid_: Opt-out, deletion request, takedown
