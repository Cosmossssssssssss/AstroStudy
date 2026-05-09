/**
 * Ambient Sound Engine — Web Audio API 纯合成
 * 参考: yanari/neuro-timer SoundContext 架构
 * 5种环境音：雨声 / 咖啡厅 / 森林 / 壁炉 / 风声
 */

class AmbientSoundEngine {
    constructor() {
        this.ctx = null;
        this.currentType = null;
        this.nodes = [];
        this.gainNode = null;
        this.masterGain = null;
        this.isPlaying = false;
        this.volume = 0.5;
    }

    _ensureCtx() {
        if (!this.ctx) {
            this.ctx = new (window.AudioContext || window.webkitAudioContext)();
            this.masterGain = this.ctx.createGain();
            this.masterGain.gain.value = this.volume;
            this.masterGain.connect(this.ctx.destination);
        }
        if (this.ctx.state === 'suspended') {
            this.ctx.resume();
        }
    }

    _stopAll() {
        this.nodes.forEach(n => {
            try { n.stop(); } catch(e) {}
            try { n.disconnect(); } catch(e) {}
        });
        this.nodes = [];
        this.isPlaying = false;
    }

    setVolume(v) {
        this.volume = Math.max(0, Math.min(1, v));
        if (this.masterGain) {
            this.masterGain.gain.setTargetAtTime(this.volume, this.ctx.currentTime, 0.05);
        }
    }

    play(type) {
        this._ensureCtx();
        if (this.currentType === type && this.isPlaying) return;
        this._stopAll();
        this.currentType = type;

        switch(type) {
            case 'rain': this._createRain(); break;
            case 'coffee': this._createCoffee(); break;
            case 'forest': this._createForest(); break;
            case 'fire': this._createFire(); break;
            case 'wind': this._createWind(); break;
        }
        this.isPlaying = true;
    }

    pause() {
        this._stopAll();
        this.isPlaying = false;
    }

    toggle(type) {
        if (this.currentType === type && this.isPlaying) {
            this.pause();
        } else {
            this.play(type);
        }
    }

    isActive(type) {
        return this.currentType === type && this.isPlaying;
    }

    // === 雨声：Brown noise + 随机滴答 ===
    _createRain() {
        // Brown noise base (like neuro-timer's brown noise)
        const bufferSize = this.ctx.sampleRate * 2;
        const buffer = this.ctx.createBuffer(2, bufferSize, this.ctx.sampleRate);
        for (let ch = 0; ch < 2; ch++) {
            const data = buffer.getChannelData(ch);
            let last = 0;
            for (let i = 0; i < bufferSize; i++) {
                const white = Math.random() * 2 - 1;
                data[i] = (last + (0.02 * white)) / 1.02;
                last = data[i];
                data[i] *= 3.5;
            }
        }
        const source = this.ctx.createBufferSource();
        source.buffer = buffer;
        source.loop = true;

        const filter = this.ctx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.value = 800;

        source.connect(filter);
        filter.connect(this.masterGain);
        source.start();
        this.nodes.push(source);

        // Rain drops — random high-freq ticks
        this._createRainDrops();
    }

    _createRainDrops() {
        const schedule = () => {
            if (!this.isPlaying) return;
            const osc = this.ctx.createOscillator();
            const g = this.ctx.createGain();
            osc.type = 'sine';
            osc.frequency.value = 2000 + Math.random() * 4000;
            g.gain.value = 0;
            g.gain.setTargetAtTime(0.03 + Math.random() * 0.04, this.ctx.currentTime, 0.001);
            g.gain.setTargetAtTime(0, this.ctx.currentTime + 0.02, 0.01);
            osc.connect(g);
            g.connect(this.masterGain);
            osc.start();
            osc.stop(this.ctx.currentTime + 0.08);
            setTimeout(schedule, 30 + Math.random() * 200);
        };
        schedule();
    }

    // === 咖啡厅：低频嗡嗡 + 偶尔碰撞声 ===
    _createCoffee() {
        // Ambient murmur — multiple detuned oscillators
        const freqs = [120, 180, 240, 300];
        freqs.forEach(f => {
            const osc = this.ctx.createOscillator();
            const g = this.ctx.createGain();
            osc.type = 'sawtooth';
            osc.frequency.value = f + Math.random() * 10;
            g.gain.value = 0.015;
            osc.connect(g);

            const filter = this.ctx.createBiquadFilter();
            filter.type = 'bandpass';
            filter.frequency.value = f;
            filter.Q.value = 2;
            g.connect(filter);
            filter.connect(this.masterGain);
            osc.start();
            this.nodes.push(osc);
        });

        // Brown noise bed
        const bufferSize = this.ctx.sampleRate * 2;
        const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
        const data = buffer.getChannelData(0);
        let last = 0;
        for (let i = 0; i < bufferSize; i++) {
            const white = Math.random() * 2 - 1;
            data[i] = (last + 0.02 * white) / 1.02;
            last = data[i];
            data[i] *= 2;
        }
        const noise = this.ctx.createBufferSource();
        noise.buffer = buffer;
        noise.loop = true;
        const nf = this.ctx.createBiquadFilter();
        nf.type = 'lowpass';
        nf.frequency.value = 400;
        noise.connect(nf);
        nf.connect(this.masterGain);
        noise.start();
        this.nodes.push(noise);

        // Random cup clinks
        this._createClinks();
    }

    _createClinks() {
        const schedule = () => {
            if (!this.isPlaying) return;
            const osc = this.ctx.createOscillator();
            const g = this.ctx.createGain();
            osc.type = 'sine';
            osc.frequency.value = 3000 + Math.random() * 3000;
            g.gain.value = 0;
            g.gain.setTargetAtTime(0.06, this.ctx.currentTime, 0.0005);
            g.gain.setTargetAtTime(0, this.ctx.currentTime + 0.01, 0.005);
            osc.connect(g);
            g.connect(this.masterGain);
            osc.start();
            osc.stop(this.ctx.currentTime + 0.05);
            setTimeout(schedule, 2000 + Math.random() * 8000);
        };
        setTimeout(schedule, 1000);
    }

    // === 森林：风声 + 鸟鸣 ===
    _createForest() {
        // Wind base
        const bufferSize = this.ctx.sampleRate * 2;
        const buffer = this.ctx.createBuffer(2, bufferSize, this.ctx.sampleRate);
        for (let ch = 0; ch < 2; ch++) {
            const data = buffer.getChannelData(ch);
            let last = 0;
            for (let i = 0; i < bufferSize; i++) {
                const white = Math.random() * 2 - 1;
                data[i] = (last + 0.01 * white) / 1.01;
                last = data[i];
                data[i] *= 2;
            }
        }
        const wind = this.ctx.createBufferSource();
        wind.buffer = buffer;
        wind.loop = true;
        const wf = this.ctx.createBiquadFilter();
        wf.type = 'bandpass';
        wf.frequency.value = 300;
        wf.Q.value = 0.5;
        wind.connect(wf);
        wf.connect(this.masterGain);
        wind.start();
        this.nodes.push(wind);

        // Bird chirps
        this._createBirds();
    }

    _createBirds() {
        const schedule = () => {
            if (!this.isPlaying) return;
            const osc = this.ctx.createOscillator();
            const g = this.ctx.createGain();
            osc.type = 'sine';
            const baseFreq = 1500 + Math.random() * 2500;
            osc.frequency.value = baseFreq;
            osc.frequency.setTargetAtTime(baseFreq + 500 * (Math.random() - 0.5), this.ctx.currentTime + 0.05, 0.03);
            g.gain.value = 0;
            g.gain.setTargetAtTime(0.04 + Math.random() * 0.03, this.ctx.currentTime, 0.002);
            g.gain.setTargetAtTime(0, this.ctx.currentTime + 0.08, 0.02);
            osc.connect(g);
            g.connect(this.masterGain);
            osc.start();
            osc.stop(this.ctx.currentTime + 0.2);
            setTimeout(schedule, 3000 + Math.random() * 10000);
        };
        setTimeout(schedule, 2000);
    }

    // === 壁炉：Crackling fire ===
    _createFire() {
        // Low rumble
        const bufferSize = this.ctx.sampleRate * 2;
        const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
        const data = buffer.getChannelData(0);
        let last = 0;
        for (let i = 0; i < bufferSize; i++) {
            const white = Math.random() * 2 - 1;
            data[i] = (last + 0.03 * white) / 1.03;
            last = data[i];
            data[i] *= 2.5;
        }
        const rumble = this.ctx.createBufferSource();
        rumble.buffer = buffer;
        rumble.loop = true;
        const rf = this.ctx.createBiquadFilter();
        rf.type = 'lowpass';
        rf.frequency.value = 300;
        rumble.connect(rf);
        rf.connect(this.masterGain);
        rumble.start();
        this.nodes.push(rumble);

        // Crackles
        this._createCrackles();
    }

    _createCrackles() {
        const schedule = () => {
            if (!this.isPlaying) return;
            const bufferSize = Math.floor(this.ctx.sampleRate * 0.05);
            const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
            const data = buffer.getChannelData(0);
            for (let i = 0; i < bufferSize; i++) {
                data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (bufferSize * 0.3));
            }
            const source = this.ctx.createBufferSource();
            source.buffer = buffer;
            const g = this.ctx.createGain();
            g.gain.value = 0.08 + Math.random() * 0.08;
            const hf = this.ctx.createBiquadFilter();
            hf.type = 'highpass';
            hf.frequency.value = 800 + Math.random() * 1000;
            source.connect(hf);
            hf.connect(g);
            g.connect(this.masterGain);
            source.start();
            setTimeout(schedule, 100 + Math.random() * 600);
        };
        setTimeout(schedule, 500);
    }

    // === 风声：Filtered noise with LFO modulation ===
    _createWind() {
        const bufferSize = this.ctx.sampleRate * 2;
        const buffer = this.ctx.createBuffer(2, bufferSize, this.ctx.sampleRate);
        for (let ch = 0; ch < 2; ch++) {
            const data = buffer.getChannelData(ch);
            for (let i = 0; i < bufferSize; i++) {
                data[i] = Math.random() * 2 - 1;
            }
        }
        const noise = this.ctx.createBufferSource();
        noise.buffer = buffer;
        noise.loop = true;

        const bp = this.ctx.createBiquadFilter();
        bp.type = 'bandpass';
        bp.frequency.value = 400;
        bp.Q.value = 1.5;

        // LFO for filter sweep
        const lfo = this.ctx.createOscillator();
        const lfoGain = this.ctx.createGain();
        lfo.type = 'sine';
        lfo.frequency.value = 0.15;
        lfoGain.gain.value = 300;
        lfo.connect(lfoGain);
        lfoGain.connect(bp.frequency);
        lfo.start();

        noise.connect(bp);
        bp.connect(this.masterGain);
        noise.start();
        this.nodes.push(noise, lfo);
    }
}

// Global singleton
window.ambientSound = new AmbientSoundEngine();
