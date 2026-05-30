import urllib3, requests, json
urllib3.disable_warnings()

url = 'https://services.ga.gov.au/gis/rest/services/Foundation_Facilities_Points/MapServer/1/query'

params = {
    'where': '1=1',
    'outStatistics': json.dumps([{'statisticType':'count','onStatisticField':'objectid','outStatisticFieldName':'n'}]),
    'groupByFieldsForStatistics': 'main_function',
    'f': 'json'
}
r = requests.get(url, params=params, verify=False, timeout=30)
data = r.json()
print('GA main_function breakdown:')
for feat in sorted(data.get('features', []), key=lambda x: -(x['attributes'].get('n') or 0)):
    a = feat['attributes']
    mf = a.get('main_function')
    n = a.get('n')
    print(f'  {mf}: {n}')

# AIHW
r2 = requests.get(
    'https://myhospitalsapi.aihw.gov.au/api/v0/retired-myhospitals-api/hospitals',
    headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
    verify=False, timeout=30
)
print()
print('AIHW status:', r2.status_code)
if r2.status_code == 200:
    hospitals = r2.json()
    print('Total hospitals:', len(hospitals))
    public_active = [h for h in hospitals if h.get('ispublic') and not h.get('isclosed')]
    private_active = [h for h in hospitals if not h.get('ispublic') and not h.get('isclosed')]
    print('  Active public:', len(public_active))
    print('  Active private/other:', len(private_active))
    print('  Sample public:', public_active[:2])
