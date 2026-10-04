/**
 * Presentation content for the VIDHIVEDA research interface.
 *
 * The case records themselves live in ./dataset.js, which is generated from
 * VIDHIVEDA_Sample_Dataset.csv (run `npm run build:dataset`). This file only
 * holds hand-written material: the reference-library list and the example
 * queries offered under the search bar.
 *
 * Every entry in `exampleQueries` is asserted to return at least one record by
 * `npm run verify:search` — keep that script green when editing this list.
 */

/**
 * Instruments referenced by the sample dataset, used for the reference library.
 * `query` is what gets searched when the user opens a card, so each one should
 * appear in the dataset's "Applicable Section(s) / Article(s)" column.
 */
export const statutes = [
  { title: 'Arbitration and Conciliation Act, 1996', category: 'Commercial', query: 'arbitration' },
  { title: 'Insolvency and Bankruptcy Code, 2016', category: 'Commercial', query: 'insolvency' },
  { title: 'Sale of Goods Act, 1930', category: 'Commercial', query: 'sale of goods' },
  { title: 'Income-tax Act, 1961', category: 'Taxation', query: 'income tax' },
  { title: 'GST Act', category: 'Taxation', query: 'gst' },
  { title: 'Customs Act, 1962', category: 'Taxation', query: 'customs' },
  { title: 'Code of Civil Procedure, 1908', category: 'Civil Procedure', query: 'cpc' },
  { title: 'Transfer of Property Act, 1882', category: 'Property', query: 'transfer of property' },
  { title: 'Specific Relief Act, 1963', category: 'Civil Procedure', query: 'specific relief' },
  { title: 'Companies Act, 2013', category: 'Corporate', query: 'companies act' },
  { title: 'Industrial Disputes Act, 1947', category: 'Labour', query: 'industrial disputes' },
  { title: 'Payment of Wages Act, 1936', category: 'Labour', query: 'wages' },
  { title: 'Employees\u2019 Compensation Act, 1923', category: 'Labour', query: 'employees compensation' },
  { title: 'Service Rules', category: 'Service Law', query: 'service rules' },
  { title: 'Administrative Tribunals Act, 1985', category: 'Service Law', query: 'administrative tribunals' },
  { title: 'Protection of Human Rights Act, 1993', category: 'Human Rights', query: 'human rights' },
  { title: 'Protection of Women from Domestic Violence Act, 2005', category: 'Family', query: 'domestic violence' },
  { title: 'Guardians and Wards Act, 1890', category: 'Family', query: 'guardians and wards' },
  { title: 'Scheduled Castes and Tribes (Prevention of Atrocities) Act, 1989', category: 'Criminal', query: 'prevention of atrocities' },
  { title: 'Information Technology Act, 2000', category: 'Cyber & Technology', query: 'it act' },
];

/**
 * Example research questions shown beneath the search bar.
 * Phrased the way a researcher would actually type them.
 */
export const exampleQueries = [
  { label: 'Natural justice in administrative action', query: 'natural justice' },
  { label: 'Constitutional validity of a provision', query: 'constitutional validity' },
  { label: 'Arbitration clause and its scope', query: 'arbitration clause' },
  { label: 'Maintenance after divorce', query: 'maintenance' },
  { label: 'Income tax assessment', query: 'income tax' },
  { label: 'GST demands and penalty', query: 'gst' },
  { label: 'Insolvency and winding up', query: 'insolvency' },
  { label: 'Land acquisition and compensation', query: 'land acquisition' },
  { label: 'Service rules and departmental action', query: 'service rules' },
  { label: 'Wages and gratuity claims', query: 'wages' },
  { label: 'Domestic violence protections', query: 'domestic violence' },
  { label: 'Specific relief and injunctions', query: 'specific relief' },
];
