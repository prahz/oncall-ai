#input_type_name: BootstrapInput
#output_type_name: BootstrapResult
#function_name: _bootstrap

# One-shot bootstrap: writes the runbook library and seeds monitored_services.
# Runs inside the pod (server-synced SDK) to sidestep the local CLI upload skew.

import base64
from io import BytesIO
from typing import List
from pydantic import BaseModel, Field
from lemma_sdk import FunctionContext, Pod

RUNBOOKS = {
    "api-gateway.md": "IyBSdW5ib29rIOKAlCBhcGktZ2F0ZXdheQoKKipUaWVyOioqIGltcG9ydGFudCDCtyByZXF1ZXN0IHJvdXRlciAoc3RhdGVsZXNzIHJlcGxpY2FzIGJlaGluZCBhIGxvYWQgYmFsYW5jZXIpCioqT3duZXI6KiogcGxhdGZvcm0gdGVhbQoqKkF1dG8tcmVtZWRpYXRpb24gc2FmZTogeWVzKioKClRoZSBnYXRld2F5IHByb3hpZXMgdHJhZmZpYyB0byBkb3duc3RyZWFtIHNlcnZpY2VzLiBSZXBsaWNhcyBhcmUgc3RhdGVsZXNzLCBzbwpyZXN0YXJ0aW5nIGFuIHVuaGVhbHRoeSByZXBsaWNhIGlzIHNhZmUgYW5kIGlzIHRoZSBzdGFuZGFyZCBmaXggZm9yIHRoZSB0d28KZmFpbHVyZSBtb2RlcyBiZWxvdy4gQSByb2xsYmFjayBpcyAqKm5vdCoqIGF1dG8tc2FmZSAoc2VlIGJvdHRvbSkuCgojIyBDb21tb24gYWxlcnRzICYgd2hhdCB0aGV5IG1lYW4KfCBTaWduYWwgfCBMaWtlbHkgY2F1c2UgfAp8IC0tLSB8IC0tLSB8CnwgcDk1IGBsYXRlbmN5X21zYCBvdmVyIHRocmVzaG9sZCwgbWVtb3J5IGhpZ2ggfCAqKkdDIHRocmFzaGluZyoqIOKAlCBoZWFwIHByZXNzdXJlIGZyb20gYSBjb25uZWN0aW9uL29iamVjdCBsZWFrLCBsb25nIEdDIHBhdXNlcyB8CnwgYGxhdGVuY3lfbXNgIHNwaWtlIHJpZ2h0IGFmdGVyIGEgZGVwbG95IHwgYmFkIGNvbmZpZyBvciBhIHJlZ3Jlc3Npb24gaW4gdGhlIG5ldyBidWlsZCB8CnwgSFRUUCA1eHggZnJvbSBgL2hlYWx0aGAgfCByZXBsaWNhIGNyYXNoZWQgb3Igd2VkZ2VkIHwKCiMjIFJlbWVkaWF0aW9uIChpbiBvcmRlcikKMS4gKipHQyB0aHJhc2hpbmcgLyBoaWdoIGxhdGVuY3kgd2l0aCBubyByZWNlbnQgZGVwbG95Kiog4oaSIGByZXN0YXJ0X3NlcnZpY2VgLgogICBBIHJlc3RhcnQgY2xlYXJzIHRoZSBsZWFrZWQgaGVhcCBhbmQgY29ubmVjdGlvbiBwb29sLiBTYWZlOiByZXBsaWNhcyBhcmUKICAgc3RhdGVsZXNzIGFuZCBkcmFpbmVkIGJ5IHRoZSBsb2FkIGJhbGFuY2VyIGZpcnN0LgoyLiBSZS1jaGVjayBgL2hlYWx0aGA6IGxhdGVuY3kgYmFjayB1bmRlciB0aHJlc2hvbGQsIG1lbW9yeSBub3JtYWwuCjMuICoqTGF0ZW5jeSBzcGlrZSB3aXRoaW4gfjE1IG1pbiBvZiBhIGRlcGxveSoqIOKGkiBgcm9sbGJhY2tfZGVwbG95YCB0byB0aGUgbGFzdAogICBnb29kIGJ1aWxkLiBSb2xsYmFjayB0b3VjaGVzIHJvdXRpbmcgY29uZmlnLCBzbyBpdCBpcyAqKm5vdCoqIGF1dG8tc2FmZSDigJQKICAgcmVxdWVzdCBodW1hbiBhcHByb3ZhbC4KNC4gSWYgYSByZXN0YXJ0IGRvZXMgbm90IGhvbGQgYWZ0ZXIgKip0d28qKiBhdHRlbXB0cywgZXNjYWxhdGUuCgojIyBOb3RlcyBmb3IgdGhlIGFuYWx5c3QKLSBHQyB0aHJhc2hpbmcgLyBsYXRlbmN5IHdpdGggYHN1c3BlY3RfZGVwbG95ID0gdW5rbm93bmAg4oeSIGByZXN0YXJ0X3NlcnZpY2VgLAogIGNvbmZpZGVuY2UgMC45Ky4KLSBMYXRlbmN5IGNsZWFybHkgdGllZCB0byBhIG5hbWVkIHJlY2VudCBkZXBsb3kg4oeSIGByb2xsYmFja19kZXBsb3lgLAogIGBydW5ib29rX3NhZmUgPSBmYWxzZWAgKG5lZWRzIGEgaHVtYW4pLgoKQXV0by1yZW1lZGlhdGlvbiBzYWZlOiB5ZXMgKHJlc3RhcnRfc2VydmljZSBvbmx5OyByb2xsYmFja19kZXBsb3kgbmVlZHMgaHVtYW4gYXBwcm92YWwpCg==",
    "automated-service.md": "IyBSdW5ib29rIOKAlCBhdXRvbWF0ZWQtc2VydmljZQoKKipUaWVyOioqIG5vbi1jcml0aWNhbCDCtyBzdGF0ZWxlc3Mgd29ya2VyCioqT3duZXI6KiogcGxhdGZvcm0gdGVhbQoqKkF1dG8tcmVtZWRpYXRpb24gc2FmZTogeWVzKioKCmBhdXRvbWF0ZWQtc2VydmljZWAgcnVucyBzbWFsbCwgc3RhdGVsZXNzLCBpZGVtcG90ZW50IGpvYnMuIEl0IGhvbGRzIG5vCnVzZXItZmFjaW5nIHN0YXRlLCBzbyBhIHJlc3RhcnQgaXMgYWx3YXlzIHNhZmUgYW5kIGlzIHRoZSBzdGFuZGFyZCBmaXJzdCBmaXguCgojIyBDb21tb24gYWxlcnRzICYgd2hhdCB0aGV5IG1lYW4KfCBTaWduYWwgfCBMaWtlbHkgY2F1c2UgfAp8IC0tLSB8IC0tLSB8CnwgYC9oZWFsdGhgIG9yIGAvcGluZ2AgdW5yZXNwb25zaXZlIC8gSFRUUCA1eHggfCBwcm9jZXNzIGh1bmcgb3IgY3Jhc2hlZCAoZXZlbnQtbG9vcCBibG9jaywgZGVhZGxvY2spIHwKfCBtZW1vcnlfcGN0IGNsaW1iaW5nIG92ZXIgdGltZSB8IHNsb3cgbGVhayBpbiBhIHdvcmtlcjsgY2xlYXJlZCBieSBhIHJlc3RhcnQgfAp8IGxhdGVuY3lfbXMgc3Bpa2UsIENQVSBub3JtYWwgfCBHQyBwYXVzZSBvciBhIHN0dWNrIGRvd25zdHJlYW0gY2FsbCB8CgojIyBSZW1lZGlhdGlvbiAoaW4gb3JkZXIpCjEuICoqUmVzdGFydCB0aGUgc2VydmljZSoqIChgcmVzdGFydF9zZXJ2aWNlYCkuIEl0IGlzIHN0YXRlbGVzcyDigJQgYSByb2xsaW5nCiAgIHJlc3RhcnQgZHJvcHMgaW4tZmxpZ2h0IGlkZW1wb3RlbnQgam9icyBzYWZlbHkgYW5kIGNsZWFycyBhIGh1bmcgcHJvY2Vzcy4KMi4gUmUtY2hlY2sgYC9oZWFsdGhgOiBleHBlY3QgYHN0YXR1czogaGVhbHRoeWAsIGxhdGVuY3kgdW5kZXIgdGhyZXNob2xkLgozLiBJZiBpdCByZWNvdmVycyDihpIgZG9uZS4gSWYgaXQgZmFpbHMgKip0d2ljZSoqLCBlc2NhbGF0ZSB0byBhIGh1bWFuIGFuZCBjaGVjawogICBsb2dzIGZvciBhIGNyYXNoIGxvb3AsIE9PTSBraWxsLCBvciBhIGJhZCByZWNlbnQgZGVwbG95LgoKIyMgTm90ZXMgZm9yIHRoZSBhbmFseXN0Ci0gQSBodW5nL3VucmVzcG9uc2l2ZSBgYXV0b21hdGVkLXNlcnZpY2VgIG1hcHMgY2xlYW5seSB0byBgcmVzdGFydF9zZXJ2aWNlYC4KLSBDbGVhciBydW5ib29rIG1hdGNoICsgc3RhdGVsZXNzIHNlcnZpY2Ug4oeSIGhpZ2ggY29uZmlkZW5jZSAoMC45KykuCgpBdXRvLXJlbWVkaWF0aW9uIHNhZmU6IHllcwo=",
    "database-cluster.md": "IyBSdW5ib29rIOKAlCBkYXRhYmFzZS1jbHVzdGVyCgoqKlRpZXI6KiogQ1JJVElDQUwgwrcgc2hhcmVkIHN0YXRlZnVsIGluZnJhc3RydWN0dXJlIChwcmltYXJ5ICsgcmVwbGljYXMpCioqT3duZXI6KiogaW5mcmEgdGVhbSDCtyBQYWdlckR1dHk6IGluZnJhLXByaW1hcnkKKipBdXRvLXJlbWVkaWF0aW9uIHNhZmU6IG5vKioKClRoZSBwcmltYXJ5IGRhdGFzdG9yZSBmb3IgdGhlIHdob2xlIHBsYXRmb3JtLiBCbGFzdCByYWRpdXMgaXMgZWZmZWN0aXZlbHkgZXZlcnkKc2VydmljZSwgYW5kIHRoZSB3cm9uZyBhY3Rpb24gKGZhaWxvdmVyLCByZXN0YXJ0LCBjYWNoZSBmbHVzaCkgY2FuIGNhdXNlIGRhdGEKbG9zcyBvciBhIGxvbmdlciBvdXRhZ2UuICoqQSBodW1hbiBhbHdheXMgYXBwcm92ZXMuKioKCiMjIENvbW1vbiBhbGVydHMgJiB3aGF0IHRoZXkgbWVhbgp8IFNpZ25hbCB8IExpa2VseSBjYXVzZSB8CnwgLS0tIHwgLS0tIHwKfCBgZGIuY29ubmVjdGlvbnMuYWN0aXZlYCBhdCB+MTAwJSBvZiBwb29sIHwgKipjb25uZWN0aW9uLXBvb2wgZXhoYXVzdGlvbioqIOKAlCBhIGNsaWVudCBsZWFraW5nIGNvbm5lY3Rpb25zIG9yIGEgdHJhZmZpYyBzdXJnZSB8CnwgcmVwbGljYSBsYWcgY2xpbWJpbmcgfCBzbG93IHF1ZXJ5IC8gbG9uZyB0cmFuc2FjdGlvbiBob2xkaW5nIGxvY2tzIHwKfCBwcmltYXJ5IGAvaGVhbHRoYCA1eHggfCBub2RlIGRvd24g4oCUIGEgY29udHJvbGxlZCBmYWlsb3ZlciBtYXkgYmUgcmVxdWlyZWQgfAoKIyMgUmVtZWRpYXRpb24gKGluIG9yZGVyIOKAlCBhbGwgcmVxdWlyZSBhcHByb3ZhbCkKMS4gKipDb25uZWN0aW9uLXBvb2wgZXhoYXVzdGlvbioqIOKGkiBpZGVudGlmeSB0aGUgb2ZmZW5kaW5nIGNsaWVudCBhbmQgcmVjeWNsZQogICAqaXRzKiBwb29sIChvciByYWlzZSB0aGUgbGltaXQpOyBkbyAqKm5vdCoqIGJsYW5rZXQtcmVzdGFydCB0aGUgY2x1c3Rlci4KICAgUmVxdWlyZXMgaHVtYW4gYXBwcm92YWwg4oCUIGEgcmVzdGFydCBkcm9wcyBldmVyeSBvcGVuIHRyYW5zYWN0aW9uLgoyLiAqKlByaW1hcnkgZG93bioqIOKGkiBjb250cm9sbGVkIGZhaWxvdmVyIHRvIGEgaGVhbHRoeSByZXBsaWNhLiBIdW1hbi1kcml2ZW4uCjMuIE5ldmVyIGF1dG8tZmx1c2ggY2FjaGVzIG9yIGZhaWwgb3ZlciBhdXRvbWF0aWNhbGx5LgoKIyMgTm90ZXMgZm9yIHRoZSBhbmFseXN0Ci0gQ29ubmVjdGlvbiBwb29sIGF0IDEwMCUg4oeSIHJvb3QgY2F1c2UgImNvbm5lY3Rpb24tcG9vbCBleGhhdXN0aW9uIiwgcHJvcG9zZSB0aGUKICB0YXJnZXRlZCBmaXgsIGBhY3Rpb25fdHlwZSA9IG1hbnVhbF9maXhfcmVxdWlyZWRgIG9yIGBub3RpZnlfdGVhbWAsCiAgYHJ1bmJvb2tfc2FmZSA9IGZhbHNlYC4KLSBDcml0aWNhbCArIGluZnJhc3RydWN0dXJlIGJsYXN0IHJhZGl1cyDih5IgYWx3YXlzIGh1bWFuIGFwcHJvdmFsLgoKQXV0by1yZW1lZGlhdGlvbiBzYWZlOiBubwo=",
    "image-processing-worker.md": "IyBSdW5ib29rIOKAlCBpbWFnZS1wcm9jZXNzaW5nLXdvcmtlcgoKKipUaWVyOioqIGltcG9ydGFudCDCtyBhc3luYyB3b3JrZXIgKHB1bGxzIGpvYnMgZnJvbSBhIHF1ZXVlKQoqKk93bmVyOioqIG1lZGlhIHRlYW0KKipBdXRvLXJlbWVkaWF0aW9uIHNhZmU6IHllcyoqCgpEZWNvZGVzIGFuZCByZXNpemVzIGltYWdlcyBvZmYgYSBqb2IgcXVldWUuIEpvYnMgYXJlIHJlLXF1ZXVlZCBvbiB3b3JrZXIgZXhpdCwKc28gYSByZXN0YXJ0IG5ldmVyIGxvc2VzIHdvcmsuIEtub3duIHRvIGxlYWsgbmF0aXZlIG1lbW9yeSBmcm9tIHRoZSBpbWFnZQpkZWNvZGVyIHVuZGVyIHN1c3RhaW5lZCBsb2FkLCB3aGljaCBlbmRzIGluIGFuIE9PTSBraWxsLgoKIyMgQ29tbW9uIGFsZXJ0cyAmIHdoYXQgdGhleSBtZWFuCnwgU2lnbmFsIHwgTGlrZWx5IGNhdXNlIHwKfCAtLS0gfCAtLS0gfAp8IGBtZW1vcnlfcGN0YCBjbGltYmluZyB0b3dhcmQgMTAwJSwgdGhlbiBPT00gfCAqKm5hdGl2ZSBtZW1vcnkgbGVhayoqIGluIHRoZSBkZWNvZGUgcGF0aCAodGhlIGNsYXNzaWMgZmFpbHVyZSkgfAp8IHdvcmtlciBgL2hlYWx0aGAgNXh4IGFmdGVyIE9PTSB8IGtlcm5lbCBPT00ta2lsbGVkIHRoZSBwcm9jZXNzOyBpdCBuZWVkcyBhIGNsZWFuIHJlc3RhcnQgfAp8IHF1ZXVlIGRlcHRoIHJpc2luZywgdGhyb3VnaHB1dCBkcm9wcGluZyB8IHdvcmtlciB3ZWRnZWQgb24gYSBwb2lzb24tcGlsbCBpbWFnZSB8CgojIyBSZW1lZGlhdGlvbiAoaW4gb3JkZXIpCjEuICoqTWVtb3J5IGxlYWsgLyBPT00ga2lsbCoqIOKGkiBgcmVzdGFydF9zZXJ2aWNlYC4gVGhlIHF1ZXVlIHJlZGVsaXZlcnMKICAgaW4tZmxpZ2h0IGpvYnMsIHNvIHRoaXMgaXMgc2FmZSBhbmQgY2xlYXJzIHRoZSBsZWFrZWQgbmF0aXZlIGhlYXAuCjIuIFJlLWNoZWNrIGAvaGVhbHRoYDogYG1lbW9yeV9wY3RgIGJhY2sgdG8gYmFzZWxpbmUsIHdvcmtlciBjb25zdW1pbmcgdGhlIHF1ZXVlLgozLiBJZiBPT00gcmVjdXJzIHdpdGhpbiBvbmUgcG9sbCBjeWNsZSBhZnRlciBhIHJlc3RhcnQsIGVzY2FsYXRlIOKAlCBsaWtlbHkgYQogICBwb2lzb24tcGlsbCBqb2Igb3IgYSByZWdyZXNzaW9uOyBhIGh1bWFuIHNob3VsZCBkcmFpbiB0aGUgcXVldWUgLyBwYXRjaCB0aGUKICAgZGVjb2Rlci4KCiMjIE5vdGVzIGZvciB0aGUgYW5hbHlzdAotIFJpc2luZyBtZW1vcnkgZW5kaW5nIGluIE9PTSDih5IgYHJlc3RhcnRfc2VydmljZWAsIGNvbmZpZGVuY2UgMC45Ky4KLSBUaGlzIGlzIGEgcmVjdXJyaW5nLCB3ZWxsLXVuZGVyc3Rvb2QgbGVhaywgc28gYXV0by1yZW1lZGlhdGlvbiBpcyBzYWZlIGZvciBhCiAgZmlyc3QgcmVzdGFydC4KCkF1dG8tcmVtZWRpYXRpb24gc2FmZTogeWVzCg==",
    "payment-service.md": "IyBSdW5ib29rIOKAlCBwYXltZW50LXNlcnZpY2UKCioqVGllcjoqKiBDUklUSUNBTCDCtyBtb25leSBwYXRoIChjYXJkIGF1dGhvcml6YXRpb24gJiBjYXB0dXJlKQoqKk93bmVyOioqIHBheW1lbnRzIHRlYW0gwrcgUGFnZXJEdXR5OiBwYXltZW50cy1wcmltYXJ5CioqQXV0by1yZW1lZGlhdGlvbiBzYWZlOiBubyoqCgpUaGlzIHNlcnZpY2UgbW92ZXMgbW9uZXkuIEV2ZXJ5IHJlbWVkaWF0aW9uIHJpc2tzIGRvdWJsZS1jaGFyZ2VzLCBkcm9wcGVkCmNhcHR1cmVzLCBvciByZWNvbmNpbGlhdGlvbiBnYXBzLCBzbyAqKmEgaHVtYW4gYWx3YXlzIGFwcHJvdmVzKiog4oCUIHRoZSBBSQpkaWFnbm9zZXMgYW5kIHByb3Bvc2VzLCBidXQgbmV2ZXIgYWN0cyBhbG9uZSBoZXJlLgoKIyMgQ29tbW9uIGFsZXJ0cyAmIHdoYXQgdGhleSBtZWFuCnwgU2lnbmFsIHwgTGlrZWx5IGNhdXNlIHwKfCAtLS0gfCAtLS0gfAp8IGBlcnJvcl9yYXRlYCBzcGlrZSArIGVsZXZhdGVkIGxhdGVuY3kgcmlnaHQgYWZ0ZXIgYSBkZXBsb3kgfCByZWdyZXNzaW9uIGluIHRoZSBuZXcgYnVpbGQgKGJhZCBTREsgdmVyc2lvbiwgdGltZW91dCBjaGFuZ2UpIHwKfCBkZWNsaW5lcy90aW1lb3V0cyB0byB0aGUgY2FyZCBwcm9jZXNzb3IgfCB1cHN0cmVhbSBwcm9jZXNzb3IgaW5jaWRlbnQgb3IgYSByb3RhdGVkIGNyZWRlbnRpYWwgfAp8IGxhdGVuY3kgY2xpbWJpbmcgd2l0aCBzdGVhZHkgZXJyb3IgcmF0ZSB8IERCIGNvbnRlbnRpb24gb3IgY29ubmVjdGlvbi1wb29sIHByZXNzdXJlIHwKCiMjIFJlbWVkaWF0aW9uIChpbiBvcmRlciDigJQgYWxsIHJlcXVpcmUgYXBwcm92YWwpCjEuICoqRXJyb3Igc3Bpa2UgdGllZCB0byBhIHJlY2VudCBkZXBsb3kqKiDihpIgcHJvcG9zZSBgcm9sbGJhY2tfZGVwbG95YCB0byB0aGUKICAgbGFzdCBrbm93bi1nb29kIGJ1aWxkLiBOYW1lIHRoZSBzdXNwZWN0IGRlcGxveS4gV2FpdCBmb3IgaHVtYW4gYXBwcm92YWwuCjIuICoqUHJvY2Vzc29yLXNpZGUgZGVjbGluZXMqKiDihpIgZG8gKipub3QqKiByb2xsIGJhY2s7IHBhZ2UgdGhlIHBheW1lbnRzCiAgIG9uLWNhbGwgYW5kIG9wZW4gYSB2ZW5kb3IgdGlja2V0LiBgbm90aWZ5X3RlYW1gLgozLiBOZXZlciByZXN0YXJ0IG1pZC10cmFuc2FjdGlvbiB3aXRob3V0IGNvbmZpcm1pbmcgaW4tZmxpZ2h0IGNhcHR1cmVzIGFyZQogICBkcmFpbmVkLgoKIyMgTm90ZXMgZm9yIHRoZSBhbmFseXN0Ci0gRGVwbG95LWxpbmtlZCBlcnJvciBzcGlrZSDih5IgYHJvbGxiYWNrX2RlcGxveWAsIG5hbWUgYHN1c3BlY3RfZGVwbG95YCwKICBjb25maWRlbmNlIGNhbiBiZSBoaWdoICoqYnV0IGBydW5ib29rX3NhZmUgPSBmYWxzZWAqKiDigJQgdGhpcyBpcyB0aGUgbW9uZXkgcGF0aC4KLSBBbHdheXMgcm91dGUgdG8gaHVtYW4gYXBwcm92YWwgcmVnYXJkbGVzcyBvZiBjb25maWRlbmNlLgoKQXV0by1yZW1lZGlhdGlvbiBzYWZlOiBubwo="
}

SERVICES = [
    {"service": "api-gateway", "enabled": False, "base_url": "https://api-gateway.internal",
     "last_status": "healthy", "last_detail": "latency 210ms, memory 46 pct"},
    {"service": "payment-service", "enabled": False, "base_url": "https://payment-service.internal",
     "last_status": "healthy", "last_detail": "error_rate 0.2 pct, latency 180ms"},
    {"service": "image-processing-worker", "enabled": False, "base_url": "https://image-worker.internal",
     "last_status": "healthy", "last_detail": "memory 38 pct, queue depth 4"},
    {"service": "automated-service", "enabled": False, "base_url": "https://automated-service.internal",
     "last_status": "healthy", "last_detail": "/ping ok, 12ms"},
]


class BootstrapInput(BaseModel):
    pass


class BootstrapResult(BaseModel):
    runbooks_written: List[str] = Field(default_factory=list)
    services_seeded: List[str] = Field(default_factory=list)
    note: str = ""


def _parse(text):
    """Pull service, title, tier and the auto_safe verdict out of a runbook."""
    title, tier, auto_safe = "", "important", False
    for line in text.splitlines():
        low = line.lower().strip()
        if not title and line.startswith("# "):
            title = line[2:].strip()
        if low.startswith("**tier:**"):
            tier = line.split("**", 2)[-1].split("·")[0].replace("Tier:", "").strip() or tier
        if "auto-remediation safe:" in low:
            auto_safe = "yes" in low.split("auto-remediation safe:", 1)[1]
    return title, tier, auto_safe


async def _bootstrap(ctx: FunctionContext, data: BootstrapInput) -> BootstrapResult:
    pod = Pod.from_env()
    written, notes = [], []

    # ---- Runbooks -> runbooks table (idempotent upsert by service) ----------
    try:
        existing_rb = {r.get("service"): r for r in
                       pod.records.list("runbooks", limit=100).to_dict()["items"]}
        for fname, b64 in RUNBOOKS.items():
            content = base64.b64decode(b64).decode("utf-8")
            service = fname[:-3] if fname.endswith(".md") else fname
            title, tier, auto_safe = _parse(content)
            row = {"service": service, "title": title or service, "tier": tier,
                   "auto_safe": auto_safe, "content": content}
            if service in existing_rb:
                pod.table("runbooks").update(existing_rb[service]["id"], row)
            else:
                pod.table("runbooks").create(row)
            written.append(f"{service}({'safe' if auto_safe else 'human'})")
    except Exception as exc:
        notes.append(f"runbooks FAILED {type(exc).__name__}: {exc}"[:220])

    # ---- Monitored services -------------------------------------------------
    seeded = []
    try:
        existing = {r.get("service") for r in
                    pod.records.list("monitored_services", limit=100).to_dict()["items"]}
        for s in SERVICES:
            if s["service"] in existing:
                continue
            pod.table("monitored_services").create(s)
            seeded.append(s["service"])
    except Exception as exc:
        notes.append(f"services FAILED {type(exc).__name__}: {exc}"[:200])

    return BootstrapResult(runbooks_written=written, services_seeded=seeded,
                           note=" | ".join(notes)[:1900] or "ok")
