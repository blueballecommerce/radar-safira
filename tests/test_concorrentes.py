import copy
import json
import unittest
from pathlib import Path
from radar.concorrentes import build, choose_main, product_page

ROOT=Path(__file__).resolve().parents[1]

class CompetitorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=json.loads((ROOT/'data/concorrentes/pesquisa-2026-09-08.json').read_text(encoding='utf-8-sig'))
        cls.obs=json.loads((ROOT/'data/concorrentes/observacoes-2026-09-08.json').read_text(encoding='utf-8-sig'))
        cls.result=build(cls.raw,cls.obs)

    def test_pagination_covers_both_sellers_and_keeps_zero_sales(self):
        self.assertEqual(sum(len(s['listings']) for s in self.result['sellers']),208)
        for s in self.result['sellers']:
            self.assertEqual(s['coverage']['sourceListings'],len(s['listings']))
            self.assertTrue(any(l['orderCount1m']==0 for l in s['listings']))

    def test_duplicate_page_fails_instead_of_silently_dropping(self):
        raw=copy.deepcopy(self.raw)
        raw['pages'].append(raw['pages'][0])
        with self.assertRaises(ValueError):
            build(raw,{})

    def test_partial_page_fails(self):
        raw=copy.deepcopy(self.raw)
        raw['pages'][-1]['data'].pop()
        with self.assertRaises(ValueError):
            build(raw,{})

    def test_best_listing_uses_monthly_then_public_sales_and_not_sum(self):
        records={'a':{'orderCount1m':10,'sold':500},'b':{'orderCount1m':20,'sold':30},'c':{'orderCount1m':20,'sold':100}}
        self.assertEqual(choose_main(records,records),'c')

    def test_missing_per_variant_sales_are_never_fabricated(self):
        for s in self.result['sellers']:
            for p in s['products']:
                self.assertIsNone(p['variantSales'])
                self.assertIsNone(p['variantRevenue'])
                if p['hasListingMetrics']:
                    self.assertFalse(any(r['referenceOnly'] for r in p['listings']))

    def test_variants_of_same_title_are_distinct(self):
        kids=next(s for s in self.result['sellers'] if s['id']=='2520649184')
        products=kids['products']
        one=next(p for p in products if p['identityKey'].endswith(':MLBU3268756501'))
        eight=next(p for p in products if p['identityKey'].endswith(':MLBU3268756509'))
        self.assertNotEqual(one['id'],eight['id'])
        self.assertIn('1 ano',one['variant'])
        self.assertIn('8 anos',eight['variant'])
        self.assertEqual(one['mainListingId'],'MLB7159766508')
        self.assertEqual(eight['mainListingId'],'MLB7159766516')

    def test_every_source_listing_is_preserved_in_a_product(self):
        for s in self.result['sellers']:
            refs={r['id'] for p in s['products'] for r in p['listings'] if not r['referenceOnly']}
            self.assertEqual(refs,{l['id'] for l in s['listings']})

    def test_same_user_product_keeps_best_listing(self):
        s=next(s for s in self.result['sellers'] if s['id']=='1806697386')
        group=next(p for p in s['products'] if any(r['id']=='MLB3699743145' and not r['referenceOnly'] for r in p['listings']))
        self.assertIn('MLB4692764964',[r['id'] for r in group['listings']])
        self.assertEqual(group['mainListingId'],'MLB4692764964')

    def test_category_redirect_is_not_a_checked_product_page(self):
        self.assertFalse(product_page({'title':'Baleiros e Bombonieres','specs':[]}))
        self.assertTrue(product_page({'title':'Kit de potes','specs':['Unidades por kit\n4']}))

    def test_different_pack_sizes_stay_separate(self):
        s=next(s for s in self.result['sellers'] if s['id']=='1806697386')
        ten={p['id'] for p in s['products'] if any(r['id']=='MLB4058978925' and not r['referenceOnly'] for r in p['listings'])}
        twenty={p['id'] for p in s['products'] if any(r['id']=='MLB4058926451' and not r['referenceOnly'] for r in p['listings'])}
        self.assertTrue(ten and twenty)
        self.assertFalse(ten & twenty)

if __name__=='__main__':
    unittest.main()
