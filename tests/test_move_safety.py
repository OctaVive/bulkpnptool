import unittest
from app import app

class MoveSafetyTests(unittest.TestCase):
    def test_invalid_pbx_ids_are_rejected(self):
        for operation, field in (('ADD', 'pbx_id_to'), ('DELETE', 'pbx_id_from'),
                                 ('MOVE', 'pbx_id_from'), ('MOVE', 'pbx_id_to')):
            for invalid in ('', '123456', '123abc7'):
                for output_format in ('csv', 'xlsx'):
                    with self.subTest(operation=operation, field=field, invalid=invalid, output_format=output_format):
                        data = dict(operation=operation, pbx_id_from='1000001', pbx_id_to='1000002',
                                    numbers='0501234567', output_format=output_format, confirm_050='1')
                        data[field] = invalid
                        response = app.test_client().post('/', data=data)
                        self.assertEqual(response.status_code, 400)
                        self.assertIn(b'must contain at least 7 digits', response.data)
                        self.assertNotIn('Content-Disposition', response.headers)

    def test_unused_pbx_field_is_not_required(self):
        for operation, field in (('ADD', 'pbx_id_to'), ('DELETE', 'pbx_id_from')):
            with self.subTest(operation=operation):
                response = app.test_client().post('/', data={
                    'operation': operation, field: '1000001', 'numbers': '0455688200',
                })
                self.assertEqual(response.status_code, 200)
                self.assertIn('Content-Disposition', response.headers)

    def test_matching_pbx_ids_are_rejected(self):
        for output_format in ('csv', 'xlsx'):
            for destination in ('1000001', ' 1000001 '):
                with self.subTest(output_format=output_format, destination=destination):
                    response = app.test_client().post('/', data=dict(operation='MOVE', pbx_id_from='1000001', pbx_id_to=destination, numbers='0501234567', output_format=output_format, confirm_050='1'))
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(b'You cannot move to the same PBX-ID', response.data)
                    self.assertNotIn('Content-Disposition', response.headers)
                    self.assertIn(b'0501234567</textarea>', response.data)

    def test_other_operations_and_distinct_move_are_allowed(self):
        for operation, destination in (('ADD', '1000001'), ('DELETE', '1000001'), ('MOVE', '1000002')):
            with self.subTest(operation=operation):
                response = app.test_client().post('/', data=dict(operation=operation, pbx_id_from='1000001', pbx_id_to=destination, numbers='0455688200', output_format='csv'))
                self.assertEqual(response.status_code, 200)
                self.assertIn('Content-Disposition', response.headers)

if __name__ == '__main__':
    unittest.main()
