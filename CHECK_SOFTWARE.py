"""Camera-free tests of target association, pan/tilt mapping, and firmware ACKs."""
import unittest
from detector import Association
from transport import Link,map_position

class Port:
    def __init__(self):self.rx=bytearray();self.tx=[]
    @property
    def in_waiting(self):return len(self.rx)
    def read(self,n):
        r=bytes(self.rx[:n]);del self.rx[:n];return r
    def write(self,data):self.tx.append(data)

class Checks(unittest.TestCase):
    def test_loss_recovery_and_class_filter(self):
        a=Association('Ball');ball=[[10,20,60,70,.8,0]]
        self.assertIsNone(a.choose(ball,0))
        self.assertIsNotNone(a.choose(ball,.1))
        self.assertIsNone(a.choose([[10,20,60,70,.9,2]],.2))
        self.assertIsNone(a.choose([],60));self.assertEqual(a.target,'Ball')
        moved=[[500,350,550,400,.9,1]]
        self.assertIsNone(a.choose(moved,61))
        self.assertEqual(a.choose(moved,61.1),(500.,350.,50.,50.))
        a=Association('Wheel');self.assertIsNone(a.choose(ball,0))

    def test_mapping_both_axes(self):
        e=(1100,1900,1200,1800)
        self.assertEqual(map_position((0,0),(640,480),e),(1100,1200))
        self.assertEqual(map_position((639,479),(640,480),e),(1900,1800))
        self.assertEqual(map_position((0,0),(640,480),e,True,True),(1900,1800))
        for x in (-100,320,10000):
            p,t=map_position((x,x),(640,480),e,gain=2)
            self.assertTrue(1100<=p<=1900 and 1200<=t<=1800)

    def test_serial_both_targets_fragmented_ack(self):
        link=Link();link.port=Port();link.send(1300,1700,force=True)
        self.assertEqual(link.port.tx[-1],b'P,1,1300,1700\n')
        link.port.rx.extend(b'ACK,1,1300,');link.poll();self.assertIsNone(link.ack)
        link.port.rx.extend(b'1700\n');link.poll();self.assertEqual(link.ack,(1300,1700))
        with self.assertRaises(ValueError):link.send(800,1500,force=True)

if __name__=='__main__':unittest.main(verbosity=2)
