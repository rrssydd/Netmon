"""Short-lived, one-use verification delivered only to the local process terminal."""
import hashlib
import secrets
import threading
import time
from collections import deque

class LocalVerification:
    def __init__(self, clock=None):
        self.clock=clock or time.monotonic
        self.lock=threading.Lock()
        self.pending={}
        self.requests=deque()

    @staticmethod
    def digest(request_id,code):
        return hashlib.sha256((request_id+':'+code).encode()).hexdigest()

    def issue(self,purpose,username,revision=None,previous=None):
        with self.lock:
            now=self.clock()
            self.pending={key:value for key,value in self.pending.items() if value['expires']>now}
            while self.requests and self.requests[0]<=now-900:self.requests.popleft()
            if self.requests and now-self.requests[-1]<30:
                raise ValueError('Silakan tunggu 30 detik sebelum meminta kode lagi.')
            if len(self.requests)>=10:
                raise ValueError('Batas permintaan kode tercapai. Coba lagi dalam 15 menit.')
            self.requests.append(now)
            if previous:self.pending.pop(previous,None)
            request_id=secrets.token_urlsafe(24)
            code=f'{secrets.randbelow(100000000):08d}'
            self.pending[request_id]=dict(purpose=purpose,username=username,revision=revision,
                digest=self.digest(request_id,code),expires=now+300,attempts=0)
            # Never return the code to a route, cookie, or browser response.
            print(f'\n[NETMON VERIFICATION] {purpose} | user {username!r}\nKode: {code}\nBerlaku 5 menit, satu kali pakai. Masukkan di halaman Netmon yang meminta kode.\n',flush=True)
            return request_id

    def consume(self,request_id,purpose,code):
        with self.lock:
            entry=self.pending.get(request_id)
            if not entry:return None
            if entry['expires']<=self.clock():
                self.pending.pop(request_id,None);return None
            if entry['purpose']!=purpose:return None
            entry['attempts']+=1
            if secrets.compare_digest(entry['digest'],self.digest(request_id,code)):
                self.pending.pop(request_id,None)
                return {key:entry[key] for key in ('username','revision')}
            if entry['attempts']>=5:self.pending.pop(request_id,None)
            return None
