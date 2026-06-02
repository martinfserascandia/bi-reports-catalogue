# IT Admin Ticket — Enable Service Principal Access to Fabric Admin API

**Requested by:** martin.falces@serascandia.com  
**Priority:** Medium  
**Estimated time:** 15 minutes

---

## Background

We have an existing app registration called **`fabric-cicd-sp`** that runs automated
security audits across our Microsoft Fabric workspaces. It needs read-only access to
the Fabric Admin REST API to retrieve which users have access to specific lakehouse
items. Without this, the audit cannot complete.

---

## App Registration Details

| Field | Value |
|---|---|
| Display name | `fabric-cicd-sp` |
| Application (Client) ID | `2592f972-96f3-4021-8179-69a38a2c0692` |
| Object ID (Service Principal) | `e7467903-fb92-47e6-85fc-581ed64137a9` |
| Tenant ID | `92c0e2e5-bda7-4705-a5a9-8b0c90300da0` |

---

## Step 1 — Check and clean the app registration (Azure Portal)

> Required role: **Application Administrator** or **Global Administrator**

1. Go to [portal.azure.com](https://portal.azure.com)
2. Navigate to **Microsoft Entra ID** → **App registrations**
3. Search for `fabric-cicd-sp` and open it
4. Click **API permissions** in the left menu
5. **Check if any of these permissions exist** (Application type, with admin consent granted):
   - Power BI Service → `Tenant.Read.All`
   - Power BI Service → `Tenant.ReadWrite.All`
   - Any other Fabric or Power BI Application permissions
6. **If any exist → remove them** by clicking the `...` next to each → Remove permission
7. Click **Save**

> **Why:** Microsoft's documentation explicitly states that if the app has admin-consent
> Application permissions for Fabric/Power BI in Azure AD, the Admin API will return
> 403 Forbidden. The correct authorization happens entirely through the Fabric Admin
> portal (Step 3), not Azure AD.

---

## Step 2 — Create a Security Group and add the service principal

> Required role: **Groups Administrator**, **User Administrator**, or **Global Administrator**

1. Go to [portal.azure.com](https://portal.azure.com)
2. Navigate to **Microsoft Entra ID** → **Groups** → **New group**
3. Fill in the form:
   - **Group type:** `Security`  ← must be Security, NOT Microsoft 365
   - **Group name:** `Fabric_Admin_API_Access`
   - **Group description:** `Allows service principals to call Fabric read-only admin APIs`
   - **Membership type:** `Assigned`
4. Click **"No members selected"**
5. In the search box, type `fabric-cicd-sp`
   - If no results appear under Users, look for an **"Enterprise applications"** or
     **"Service principals"** filter/tab in the search panel
   - Alternatively, search by the Object ID: `e7467903-fb92-47e6-85fc-581ed64137a9`
6. Select `fabric-cicd-sp` → click **Select**
7. Click **Create**
8. Open the newly created group → **Overview** → copy the **Object ID** (a GUID)
   and send it to martin.falces@serascandia.com

> **Note:** If the service principal does not appear in the member search UI, use
> PowerShell to add it after creating the group (see Appendix A below).

---

## Step 3 — Enable service principal access in Fabric Admin portal

> Required role: **Fabric Administrator** or **Global Administrator**

1. Go to [app.fabric.microsoft.com](https://app.fabric.microsoft.com)
2. Click the **gear icon (Settings)** in the top-right → **Admin portal**
3. In the left menu click **Tenant settings**
4. Search for **"Service principals can access read-only admin APIs"**
5. Click on the setting to expand it
6. Toggle it **On**
7. Under "Apply to", select **"Specific security groups"**
8. Click **"Add security groups"** and search for `Fabric_Admin_API_Access`
9. Select it and click **Apply**
10. Wait approximately **5–10 minutes** for the setting to propagate

---

## Step 4 — Verify it works

Once the above is complete, notify martin.falces@serascandia.com.
Martin will run the following test from his machine:

```
python test_lakehouse_access.py
```

Expected result — **Test 1 should return HTTP 200** with a list of users:

```
--- Test 1: Fabric scope, Fabric Admin endpoint ---
=== Budget_LH ===================================
   Status: 200
   Response keys: ['accessEntities', 'continuationUri']
```

If it still returns 403, check that:
- Step 1 was completed (no Fabric/PBI Application permissions on the app)
- The security group from Step 2 contains `fabric-cicd-sp` as a member
- The Fabric Admin portal setting from Step 3 points to that security group
- At least 10 minutes have passed since Step 3

---

## Appendix A — Add service principal to group via PowerShell

If the portal member search doesn't find the service principal, run this in
PowerShell after the group is created (replace `<GROUP-OBJECT-ID>` with the
Object ID from Step 2):

```powershell
az login --tenant "92c0e2e5-bda7-4705-a5a9-8b0c90300da0"

az rest --method POST `
  --url "https://graph.microsoft.com/v1.0/groups/<GROUP-OBJECT-ID>/members/`$ref" `
  --body "{""@odata.id"": ""https://graph.microsoft.com/v1.0/directoryObjects/e7467903-fb92-47e6-85fc-581ed64137a9""}"
```

Verify the member was added:

```powershell
az ad group member list --group "<GROUP-OBJECT-ID>" --query "[].displayName" --output tsv
```

Expected output: `fabric-cicd-sp`
