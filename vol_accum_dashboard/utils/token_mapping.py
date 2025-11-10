"""Token mapping utilities and pre-built mappings for top tokens."""

from typing import Dict, Optional
import asyncio
import aiohttp
from vol_accum_dashboard.config import COINGECKO_API_BASE, COINGECKO_REQUEST_DELAY


# Pre-built mapping for top 100 tokens (most common across exchanges)
# Format: symbol -> (contract_address, chain, coingecko_id, name)
TOP_TOKENS_MAPPING = {
    # Native assets
    "BTC": (None, "bitcoin", "bitcoin", "Bitcoin"),
    "ETH": (None, "ethereum", "ethereum", "Ethereum"),
    "BNB": (None, "binance-smart-chain", "binancecoin", "BNB"),
    "SOL": (None, "solana", "solana", "Solana"),
    "XRP": (None, "ripple", "ripple", "XRP"),
    "ADA": (None, "cardano", "cardano", "Cardano"),
    "DOGE": (None, "dogecoin", "dogecoin", "Dogecoin"),
    "TRX": (None, "tron", "tron", "TRON"),
    "DOT": (None, "polkadot", "polkadot", "Polkadot"),
    "MATIC": (None, "polygon", "matic-network", "Polygon"),
    "LTC": (None, "litecoin", "litecoin", "Litecoin"),
    "AVAX": (None, "avalanche", "avalanche-2", "Avalanche"),
    "SHIB": ("0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE", "ethereum", "shiba-inu", "Shiba Inu"),
    "ATOM": (None, "cosmos", "cosmos", "Cosmos Hub"),
    "UNI": ("0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984", "ethereum", "uniswap", "Uniswap"),
    "XLM": (None, "stellar", "stellar", "Stellar"),
    "XMR": (None, "monero", "monero", "Monero"),
    "BCH": (None, "bitcoin-cash", "bitcoin-cash", "Bitcoin Cash"),
    "LINK": ("0x514910771AF9Ca656af840dff83E8264EcF986CA", "ethereum", "chainlink", "Chainlink"),
    "ETC": (None, "ethereum-classic", "ethereum-classic", "Ethereum Classic"),

    # Stablecoins
    "USDT": ("0xdAC17F958D2ee523a2206206994597C13D831ec7", "ethereum", "tether", "Tether"),
    "USDC": ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "ethereum", "usd-coin", "USD Coin"),
    "BUSD": ("0x4Fabb145d64652a948d72533023f6E7A623C7C53", "ethereum", "binance-usd", "Binance USD"),
    "DAI": ("0x6B175474E89094C44Da98b954EedeAC495271d0F", "ethereum", "dai", "Dai"),
    "TUSD": ("0x0000000000085d4780B73119b644AE5ecd22b376", "ethereum", "true-usd", "TrueUSD"),
    "USDD": ("0x0C10bF8FcB7Bf5412187A595ab97a3609160b5c6", "ethereum", "usdd", "USDD"),
    "FDUSD": ("0xc5f0f7b66764F6ec8C8Dff7BA683102295E16409", "ethereum", "first-digital-usd", "First Digital USD"),

    # DeFi tokens
    "AAVE": ("0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9", "ethereum", "aave", "Aave"),
    "MKR": ("0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2", "ethereum", "maker", "Maker"),
    "SNX": ("0xC011a73ee8576Fb46F5E1c5751cA3B9Fe0af2a6F", "ethereum", "havven", "Synthetix"),
    "COMP": ("0xc00e94Cb662C3520282E6f5717214004A7f26888", "ethereum", "compound-governance-token", "Compound"),
    "CRV": ("0xD533a949740bb3306d119CC777fa900bA034cd52", "ethereum", "curve-dao-token", "Curve DAO"),
    "SUSHI": ("0x6B3595068778DD592e39A122f4f5a5cF09C90fE2", "ethereum", "sushi", "SushiSwap"),
    "YFI": ("0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e", "ethereum", "yearn-finance", "yearn.finance"),
    "1INCH": ("0x111111111117dC0aa78b770fA6A738034120C302", "ethereum", "1inch", "1inch"),
    "BAL": ("0xba100000625a3754423978a60c9317c58a424e3D", "ethereum", "balancer", "Balancer"),

    # Layer 2 & Scaling
    "ARB": ("0xB50721BCf8d664c30412Cfbc6cf7a15145234ad1", "arbitrum", "arbitrum", "Arbitrum"),
    "OP": ("0x4200000000000000000000000000000000000042", "optimism", "optimism", "Optimism"),
    "IMX": ("0xF57e7e7C23978C3cAEC3C3548E3D615c346e79fF", "ethereum", "immutable-x", "Immutable X"),
    "LRC": ("0xBBbbCA6A901c926F240b89EacB641d8Aec7AEafD", "ethereum", "loopring", "Loopring"),

    # Gaming & Metaverse
    "SAND": ("0x3845badAde8e6dFF049820680d1F14bD3903a5d0", "ethereum", "the-sandbox", "The Sandbox"),
    "MANA": ("0x0F5D2fB29fb7d3CFeE444a200298f468908cC942", "ethereum", "decentraland", "Decentraland"),
    "AXS": ("0xBB0E17EF65F82Ab018d8EDd776e8DD940327B28b", "ethereum", "axie-infinity", "Axie Infinity"),
    "GALA": ("0x15D4c048F83bd7e37d49eA4C83a07267Ec4203dA", "ethereum", "gala", "Gala"),
    "ENJ": ("0xF629cBd94d3791C9250152BD8dfBDF380E2a3B9c", "ethereum", "enjincoin", "Enjin Coin"),

    # Meme coins
    "PEPE": ("0x6982508145454Ce325dDbE47a25d4ec3d2311933", "ethereum", "pepe", "Pepe"),
    "FLOKI": ("0xcf0C122c6b73ff809C693DB761e7BaeBe62b6a2E", "ethereum", "floki", "FLOKI"),
    "BONK": ("DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "solana", "bonk", "Bonk"),

    # Exchange tokens
    "CRO": ("0xA0b73E1Ff0B80914AB6fe0444E65848C4C34450b", "ethereum", "crypto-com-chain", "Cronos"),
    "LEO": ("0x2AF5D2aD76741191D15Dfe7bF6aC92d4Bd912Ca3", "ethereum", "leo-token", "LEO Token"),
    "OKB": ("0x75231F58b43240C9718Dd58B4967c5114342a86c", "ethereum", "okb", "OKB"),
    "HT": ("0x6f259637dcD74C767781E37Bc6133cd6A68aa161", "ethereum", "huobi-token", "Huobi Token"),
    "FTT": ("0x50D1c9771902476076eCFc8B2A83Ad6b9355a4c9", "ethereum", "ftx-token", "FTX Token"),

    # AI & Data
    "FET": ("0xaea46A60368A7bD060eec7DF8CBa43b7EF41Ad85", "ethereum", "fetch-ai", "Fetch.ai"),
    "RNDR": ("0x6De037ef9aD2725EB40118Bb1702EBb27e4Aeb24", "ethereum", "render-token", "Render Token"),
    "GRT": ("0xc944E90C64B2c07662A292be6244BDf05Cda44a7", "ethereum", "the-graph", "The Graph"),
    "OCEAN": ("0x967da4048cD07aB37855c090aAF366e4ce1b9F48", "ethereum", "ocean-protocol", "Ocean Protocol"),

    # Privacy
    "ZEC": (None, "zcash", "zcash", "Zcash"),
    "DASH": (None, "dash", "dash", "Dash"),

    # Others
    "APE": ("0x4d224452801ACEd8B2F0aebE155379bb5D594381", "ethereum", "apecoin", "ApeCoin"),
    "LDO": ("0x5A98FcBEA516Cf06857215779Fd812CA3beF1B32", "ethereum", "lido-dao", "Lido DAO"),
    "RPL": ("0xD33526068D116cE69F19A9ee46F0bd304F21A51f", "ethereum", "rocket-pool", "Rocket Pool"),
    "BLUR": ("0x5283D291DBCF85356A21bA090E6db59121208b44", "ethereum", "blur", "Blur"),
    "STX": (None, "stacks", "blockstack", "Stacks"),
    "NEAR": (None, "near", "near", "NEAR Protocol"),
    "ALGO": (None, "algorand", "algorand", "Algorand"),
    "VET": (None, "vechain", "vechain", "VeChain"),
    "ICP": (None, "internet-computer", "internet-computer", "Internet Computer"),
    "FIL": (None, "filecoin", "filecoin", "Filecoin"),
    "APT": (None, "aptos", "aptos", "Aptos"),
    "SUI": (None, "sui", "sui", "Sui"),
    "SEI": (None, "sei", "sei-network", "Sei"),
    "INJ": ("0xe28b3B32B6c345A34Ff64674606124Dd5Aceca30", "ethereum", "injective-protocol", "Injective"),
    "TIA": (None, "celestia", "celestia", "Celestia"),
    "WLD": ("0x163f8C2467924be0ae7B5347228CABF260318753", "ethereum", "worldcoin", "Worldcoin"),
    "RUNE": (None, "thorchain", "thorchain", "THORChain"),
    "HBAR": (None, "hedera", "hedera-hashgraph", "Hedera"),
    "QNT": ("0x4a220E6096B25EADb88358cb44068A3248254675", "ethereum", "quant-network", "Quant"),
    "EGLD": (None, "multiversx", "elrond-erd-2", "MultiversX"),
    "FTM": ("0x4E15361FD6b4BB609Fa63C81A2be19d873717870", "ethereum", "fantom", "Fantom"),
    "XTZ": (None, "tezos", "tezos", "Tezos"),
    "EOS": (None, "eos", "eos", "EOS"),
    "THETA": ("0x3883f5e181fccaF8410FA61e12b59BAd963fb645", "ethereum", "theta-token", "Theta Network"),
    "KAVA": (None, "kava", "kava", "Kava"),
    "FLOW": (None, "flow", "flow", "Flow"),
    "MINA": (None, "mina", "mina-protocol", "Mina Protocol"),
    "ZIL": ("0x05f4a42e251f2d52b8ed15E9FEdAacFcEF1FAD27", "ethereum", "zilliqa", "Zilliqa"),
    "CHZ": ("0x3506424F91fD33084466F402d5D97f05F8e3b4AF", "ethereum", "chiliz", "Chiliz"),
    "BAT": ("0x0D8775F648430679A709E98d2b0Cb6250d2887EF", "ethereum", "basic-attention-token", "Basic Attention Token"),
    "ZRX": ("0xE41d2489571d322189246DaFA5ebDe1F4699F498", "ethereum", "0x", "0x Protocol"),
}


class TokenMapper:
    """Maps exchange trading pairs to unified token IDs with contract addresses."""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache: Dict[str, tuple] = TOP_TOKENS_MAPPING.copy()

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()

    def get_token_id(
        self,
        symbol: str,
        contract_address: Optional[str] = None,
        chain: Optional[str] = None,
    ) -> str:
        """Generate a unique token ID."""
        symbol = symbol.upper()

        if contract_address and chain:
            return f"{symbol}_{contract_address}_{chain}"
        elif contract_address:
            return f"{symbol}_{contract_address}_unknown"
        else:
            # Use pre-built mapping or fall back to symbol_native
            if symbol in self.cache:
                _, chain_from_cache, _, _ = self.cache[symbol]
                return f"{symbol}_native_{chain_from_cache}"
            return f"{symbol}_native_unknown"

    async def get_token_info(self, symbol: str) -> Optional[tuple]:
        """
        Get token info (contract_address, chain, coingecko_id, name).
        First checks cache, then queries CoinGecko if not found.
        """
        symbol = symbol.upper()

        # Check cache first
        if symbol in self.cache:
            return self.cache[symbol]

        # Try to fetch from CoinGecko
        try:
            info = await self._fetch_from_coingecko(symbol)
            if info:
                self.cache[symbol] = info
                return info
        except Exception as e:
            print(f"Error fetching token info for {symbol}: {e}")

        return None

    async def _fetch_from_coingecko(self, symbol: str) -> Optional[tuple]:
        """Fetch token information from CoinGecko API."""
        session = await self.get_session()

        # Search for the token
        search_url = f"{COINGECKO_API_BASE}/search"
        try:
            async with session.get(search_url, params={"query": symbol}) as response:
                if response.status == 200:
                    data = await response.json()
                    coins = data.get("coins", [])

                    # Find exact symbol match
                    for coin in coins:
                        if coin.get("symbol", "").upper() == symbol:
                            coingecko_id = coin.get("id")
                            name = coin.get("name")

                            # Get contract address
                            await asyncio.sleep(COINGECKO_REQUEST_DELAY)
                            coin_url = f"{COINGECKO_API_BASE}/coins/{coingecko_id}"
                            async with session.get(coin_url) as coin_response:
                                if coin_response.status == 200:
                                    coin_data = await coin_response.json()
                                    platforms = coin_data.get("platforms", {})

                                    # Prefer Ethereum mainnet
                                    contract_address = platforms.get("ethereum")
                                    chain = "ethereum"

                                    # If not on Ethereum, use first available
                                    if not contract_address and platforms:
                                        chain = list(platforms.keys())[0]
                                        contract_address = platforms[chain]

                                    return (contract_address, chain, coingecko_id, name)

                await asyncio.sleep(COINGECKO_REQUEST_DELAY)

        except Exception as e:
            print(f"CoinGecko API error for {symbol}: {e}")

        return None

    async def map_exchange_pair(
        self,
        exchange: str,
        base: str,
        quote: str,
        contract_info: Optional[Dict] = None,
    ) -> tuple[str, str]:
        """
        Map an exchange trading pair to a unified token ID.
        Returns (base_token_id, quote_token_id).
        """
        # Get base token info
        base_info = await self.get_token_info(base)
        if base_info:
            base_contract, base_chain, _, _ = base_info
            base_token_id = self.get_token_id(base, base_contract, base_chain)
        else:
            base_token_id = self.get_token_id(base, None, None)

        # Get quote token info
        quote_info = await self.get_token_info(quote)
        if quote_info:
            quote_contract, quote_chain, _, _ = quote_info
            quote_token_id = self.get_token_id(quote, quote_contract, quote_chain)
        else:
            quote_token_id = self.get_token_id(quote, None, None)

        return base_token_id, quote_token_id

    def get_metadata(self, symbol: str) -> Optional[Dict]:
        """Get metadata for a token from cache."""
        symbol = symbol.upper()
        if symbol in self.cache:
            contract, chain, coingecko_id, name = self.cache[symbol]
            return {
                "symbol": symbol,
                "name": name,
                "contract_address": contract,
                "chain": chain,
                "coingecko_id": coingecko_id,
            }
        return None
