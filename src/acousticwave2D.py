import numpy as np
import matplotlib.pyplot as plt
import numba
from numba import jit
import pandas as pd
    
# def v(nx, nz, v1=1500, v2=2000, v3=3000):
#     vp = np.zeros([nz,nx])
#     vp[0:int(nz/4),:]= v1
#     vp[int(nz/4):int(nz/2),:] = v2
#     vp[int(nz/2):nz,:] = v3
#     return vp

def v(nx, nz, v1=3000, v2=4000):
    vp = np.zeros([nz,nx])
    vp[0:int(nz/2),:]= v1
    vp[int(nz/2):nz,:] = v2
    return vp

def ler_modelo(caminho_arquivo, shape):
    vp = np.fromfile(caminho_arquivo, dtype=np.float32)
    vp = vp.reshape(shape).T
    print(f"Modelo de velocidade carregado de: {caminho_arquivo}")
    return vp

def expand_vp(v,nx_abc,nz_abc, N):
    v_expand = np.zeros((nz_abc, nx_abc))
    v_expand[N:nz_abc-N, N:nx_abc-N] = v
    v_expand[0:N, N:nx_abc-N] = v[0, :]
    v_expand[nz_abc-N:nz_abc, N:nx_abc-N] = v[-1, :]
    v_expand[N:nz_abc-N, 0:N] = v[:, 0:1]
    v_expand[N:nz_abc-N, nx_abc-N:nx_abc] = v[:, -1:]
    v_expand[0:N, 0:N] = v[0, 0]
    v_expand[0:N, nx_abc-N:nx_abc] = v[0, -1]
    v_expand[nz_abc-N:nz_abc, 0:N] = v[-1, 0]
    v_expand[nz_abc-N:nz_abc, nx_abc-N:nx_abc] = v[-1, -1]
    return v_expand


def ricker(f0, t):
    pi = np.pi
    td  = t - 2 * np.sqrt(pi) / f0
    fcd = f0 / (np.sqrt(pi) * 3) 
    source = (1 - 2 * pi * (pi * fcd * td) * (pi * fcd * td)) * np.exp(-pi * (pi * fcd * td) * (pi * fcd * td))
    return source

def ondas(nx,nz):
    u_anterior = np.zeros((nz,nx))
    u = np.zeros((nz,nx))
    u_posterior = np.zeros((nz,nx))
    return u_anterior, u, u_posterior

def borda (nx,nz,fator, N):
    A = np.ones((nz, nx))
    sb = 3*N 
    for i in range(nx):
        for j in range(nz):
            if i < N:  
                fb = (N - i) / (np.sqrt(2) * sb)
                A[j, i] *= np.exp(-fb * fb)
            elif i >= nx - N: 
                fb = (i - (nx - N)) / (np.sqrt(2) * sb)
                A[j, i] *= np.exp(-fb * fb)
            if j < N:  
                fb = (N - j) / (np.sqrt(2) * sb)
                A[j, i] *= np.exp(-fb * fb)
            elif j >= nz - N:  
                fb = (j - (nz - N)) / (np.sqrt(2) * sb)
                A[j, i] *= np.exp(-fb * fb)
    return A


# @numba.jit(parallel=True, nopython=True)
# def marcha_no_espaço(u_anterior, u, u_posterior, nx, nz, c, dt, dx, dz):
#     for i in numba.prange(2, nx - 3):
#         for j in numba.prange(2, nz - 3):
#             pxx = (-u[j, i+2] + 16*u[j, i+1] - 30*u[j, i] + 16*u[j, i-1] - u[j, i-2]) / (12 * dx * dx)
#             pzz = (-u[j+2, i] + 16*u[j+1, i] - 30*u[j, i] + 16*u[j-1, i] - u[j-2, i]) / (12 * dz * dz)
#             u_posterior[j, i] = (c[j, i] ** 2) * (dt ** 2) * (pxx + pzz) + 2 * u[j, i] - u_anterior[j, i]
#     return u_posterior


@numba.jit(parallel=True, nopython=True)
def marcha_no_espaço(u_anterior, u, u_posterior, nx, nz, c, dt, dx, dz):
    c0 = -205 / 72
    c1 = 8 / 5
    c2 = -1 / 5
    c3 = 8 / 315
    c4 = -1 / 560
    for i in numba.prange(4, nx - 4):  
        for j in numba.prange(4, nz - 4):  
            pxx = (c0 * u[j, i] + c1 * (u[j, i+1] + u[j, i-1]) + c2 * (u[j, i+2] + u[j, i-2]) +c3 * (u[j, i+3] + u[j, i-3]) +c4 * (u[j, i+4] + u[j, i-4])) / (dx * dx)
            pzz = (c0 * u[j, i] + c1 * (u[j+1, i] + u[j-1, i]) + c2 * (u[j+2, i] + u[j-2, i]) + c3 * (u[j+3, i] + u[j-3, i]) + c4 * (u[j+4, i] + u[j-4, i])) / (dz * dz)
            u_posterior[j, i] = (c[j, i] ** 2) * (dt ** 2) * (pxx + pzz) + 2 * u[j, i] - u_anterior[j, i]
    return u_posterior

def marcha_no_tempo(u_anterior, u, u_posterior, source, nt, nx, nz, c, recx, recz, dt, A, shot_x, shot_z, dx, dz, frame ):
    sism_shot = []
    u_snapshot = []
    for i_shot, (sx, sz) in enumerate(zip(shot_x, shot_z)):
        u_anterior.fill(0)  
        u.fill(0)
        u_posterior.fill(0)
        sism = np.zeros((nt, len(recx)))
        for k in range(nt):
            u[sz,sx]= u[sz,sx] + source[k]
            u_posterior = marcha_no_espaço(u_anterior, u, u_posterior, nx, nz, c, dt, dx, dz) 
            u_posterior *= A
            u_anterior = np.copy(u)
            u_anterior *= A 
            u = np.copy(u_posterior)

            sism[k, :] = u[recz, recx]
            if k == frame:
                u_snapshot.append(u.copy())

        sism_shot.append(sism)
    return sism_shot , u_snapshot
                         
def snapshot(p_snapshot, shot, frame):
    p_cut = p_snapshot[shot][N:-N, N:-N]
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.imshow(p_cut, cmap='gray')
    plt.title(f"Snapshot no frame {frame} para o shot {shot}")
    plt.show()
    # filename = f'../ModelagemSismica/outputs/snapshots/snapshot_frame_{frame}_shot_{shot}_nx_{p_cut.shape[1]}_nz_{p_cut.shape[0]}vti.bin'
    # p_cut.astype(np.float32).tofile(filename)
    # print(f"Snapshot do frame {frame} salvo em: {filename}")

                    
def plot_shot(sism_shot):
    for i in range(len(sism_shot)):
        perc = np.percentile(sism_shot[i], 99)
        plt.imshow(sism_shot[i], aspect='auto', cmap='gray', vmin=-perc, vmax=perc)
        plt.colorbar(label='Amplitude')
        plt.title(" shot %s"%i)
        plt.show()
    for i, shot in enumerate(sism_shot):
        filename = f'../ModelagemSismica/outputs/seismograms/sismograma_shot_{i}_{shot.shape[0]}x{shot.shape[1]}.bin'
        print(filename)
        shot.tofile(filename)
       
receiverTable = pd.read_csv("../ModelagemSismica/inputs/receivers.csv")
sourceTable = pd.read_csv("../ModelagemSismica/inputs/sources.csv")
rec_x = receiverTable['coordx'].to_numpy()
rec_z = receiverTable['coordz'].to_numpy()
shot_x = sourceTable['coordx'].to_numpy()
shot_z = sourceTable['coordz'].to_numpy()

T = 2 
dt = 0.0005

# L  = 5730
# H = 2100
# dx = 15
# dz = 15
L = 5000
H = 5000
dx = 10
dz = 10
N = 100

nx = int(L/dx) + 1
nz = int(H/dz) + 1
nt = int(T/dt) + 1

nx_abc = nx + 2*N
nz_abc = nz + 2*N

rec_x = np.round(rec_x/dx).astype(int) + N 
rec_z = np.round(rec_z/dz).astype(int) + N
shot_x = np.round(shot_x/dx).astype(int) + N
shot_z = np.round(shot_z/dz).astype(int) + N

t = np.linspace(0, T, nt, endpoint=False)

f0 = 60
source = ricker(f0, t)

c = v(nx,nz)
# c = ler_modelo('../inputs/marmousi_vp_383x141.bin', (nx, nz))
c_expand = expand_vp(c,nx_abc,nz_abc, N)

plt.figure()
plt.plot(shot_x,shot_z,"r*", markersize=5)
plt.plot(rec_x,rec_z,'bv',markersize = 2)
plt.imshow(c_expand,aspect='equal')
plt.show()

#critérios de dispersão e estabilidade
vp_min= np.min(c_expand)
vp_max = np.max(c_expand)
lambda_min = vp_min / f0
dx_lim = lambda_min / 5
dt_lim = dx_lim / (4 * vp_max)
if (dt<=dt_lim and dx<=dx_lim):
    print("Condições de estabilidade e dispersão satisfeitas")
else:
    print("Condições de estabilidade e dispersão não satisfeitas")
    print("dt_critical = %f dt = %f" %(dt_lim,dt))
    print("dx_critical = %f dx = %f" %(dx_lim,dx))
    print("fcut = %f " %(f0))

u_anterior, u, u_posterior = ondas(nx_abc,nz_abc)
A = borda(nx_abc, nz_abc, 0.015, N)
frame = 2000
sism_shot, u_snapshot = marcha_no_tempo(u_anterior, u, u_posterior, source, nt, nx_abc, nz_abc, c_expand, rec_x, rec_z, dt, A, shot_x, shot_z, dx, dz,frame)
sism_shot = sism_shot[::-1]
u_snapshot = u_snapshot[::-1]
plot_shot(sism_shot)
snapshot(u_snapshot, 0, frame)

