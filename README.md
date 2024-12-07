# FingerGuardBrowser - 隐私保护指纹浏览器

FingerGuardBrowser 是一款基于 Chromium 浏览器的指纹驱动浏览器，专注于提供高度的隐私和指纹保护。它无需注册登录，并且是完全免费的，浏览器设计用于满足外贸电商用户和注重海外隐私的用户的需求。

## 为什么选择 FingerGuardBrowser？
- 隐私保护: 修改硬件指纹、WebRTC、Canvas 和 WebGL 指纹，降低用户被追踪的风险。
- 多账户支持: 支持多个用户配置文件，每个配置文件可以定制不同的用户代理、语言、分辨率等信息，轻松切换不同的商业身份。
- SOCKS5 代理支持: 集成 SOCKS5 代理功能，用户可以选择匿名地浏览互联网。
- 操作系统定制: 根据用户需求选择不同的操作系统进行模拟，提升隐私保护水平。
- 免费: FingerGuardBrowser 是完全免费的浏览器，致力于为外贸电商用户提供更安全、更私密的在线体验。

## Setup
1. Install Python 3.8+
2. Install requirements:
```bash
pip install -r requirements.txt
```

## Project Structure
```
FingerGuardBrowser/
├── src/                    # Source code
│   ├── browser/           # Browser core functionality
│   ├── fingerprint/       # Fingerprint management
│   ├── profiles/          # Profile handling
│   └── utils/             # Utility functions
├── tests/                 # Test files
├── requirements.txt       # Project dependencies
└── README.md             # Project documentation
```

## License
MIT License
