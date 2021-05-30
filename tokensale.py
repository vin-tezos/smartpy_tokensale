import smartpy as sp

TZIP16_Metadata_Base = {
    "name"          : "Tokensale Smart Contract Template",
    "description"   : "Deploy your own token sale smart contract!",
    "authors"       : [
        "Vincent <vincent.lim@tzapac.com>"
    ],
    "homepage"      : "https://twitter.com/TzApac",
    "interfaces"    : [
        "TZIP-016"
    ],
}

# metadata = {
#             **TZIP16_Metadata_Base,
#             "views"         : views
#         }

#         self.init_metadata("metadata", metadata)


# A collection of error messages used in the contract.
class Error:
    def make(s): return (s)
    
    NotAdmin                        = make("NotAdmin")
    RequirementNotMet               = make("RequirementNotMet")
    SalePaused                      = make("SalePaused")
    SaleEnded                       = make("SaleEnded")
    NotWhitelisted                  = make("NotWhitelisted")
    InidividualExceed               = make("InidividualExceed")
    MaxExceed                       = make("MaxExceed")

class crowdsale(sp.Contract):
    def __init__(self,admin,token_address,token_id,rate,cap,max_raise,startTime, endTime):
        self.init(
            administrator = admin,
            token_address = token_address,
            token_id = token_id,
            rate = rate,
            individual_cap = cap,
            maximum_raise = max_raise,
            amountRaised = 0,
            startTime = startTime,
            endTime = endTime,
            paused = False,
            ended = False,
            whitelistedAddresses = sp.set(t = sp.TAddress),
            contributions = sp.big_map(tkey = sp.TAddress, tvalue = sp.TNat)
            )
        
        metadata = {
            **TZIP16_Metadata_Base
        }
        
        self.init_metadata("metadata", metadata)
    
    @sp.entry_point
    def buyTokens(self):
        #current transaction amount: sp.amount
        #check if user is whitelisted
        sp.verify(~self.data.paused, Error.SalePaused)
        sp.verify(self.data.ended == False,Error.SaleEnded)
        sp.verify(self.data.whitelistedAddresses.contains(sp.sender),Error.NotWhitelisted)
        contributed = self.data.contributions.get(sp.sender, 0)
        indi_total = sp.utils.mutez_to_nat(sp.amount) + contributed
        total = indi_total + self.data.amountRaised
        sp.verify(indi_total <= self.data.individual_cap, Error.InidividualExceed)
        sp.verify(total <= self.data.maximum_raise, Error.MaxExceed)
        self.data.contributions[sp.sender] = indi_total
        self.data.amountRaised += sp.utils.mutez_to_nat(sp.amount)
        sp.if self.data.amountRaised >= self.data.maximum_raise:
            self.data.ended = True
        self._transferToken(sp.record(to_address = sp.sender, amount = sp.utils.mutez_to_nat(sp.amount) * self.data.rate))    
        
    
    @sp.entry_point
    def addToWhitelist(self,params):
        sp.set_type(params, sp.TAddress)
        sp.verify(sp.sender == self.data.administrator, Error.NotAdmin)
        sp.if ~self.data.whitelistedAddresses.contains(params):
            self.data.whitelistedAddresses.add(params)
    
    @sp.entry_point
    def addMultipleWhitelist(self,params):
        sp.set_type(params, sp.TList(t = sp.TAddress))
        sp.verify(sp.sender == self.data.administrator, Error.NotAdmin)
        sp.for candidate in params:
            sp.if ~self.data.whitelistedAddresses.contains(candidate):
                self.data.whitelistedAddresses.add(candidate)
    
    @sp.entry_point
    def changeAdmin(self,params):
        sp.set_type(params, sp.TAddress)
        sp.verify(sp.sender == self.data.administrator, Error.NotAdmin)
        self.data.administrator = params
        
    @sp.entry_point
    def pauseSale(self):
        sp.verify(sp.sender == self.data.administrator, Error.NotAdmin)
        self.data.paused = True
        
    @sp.entry_point
    def unpauseSale(self):
        sp.verify(sp.sender == self.data.administrator, Error.NotAdmin)
        self.data.paused = False
    
    @sp.entry_point
    def withdrawFunds(self):
        sp.verify(sp.sender == self.data.administrator, Error.NotAdmin)
        able = sp.local("able", False)
        time_abled = sp.local("time_abled", False)
        sp.if self.data.ended:
            able.value = True
        sp.if sp.now >= self.data.endTime:
            time_abled.value = True
        sp.verify(able.value | time_abled.value, Error.RequirementNotMet)
        sp.send(sp.sender,sp.balance)
            
    def _transferToken(self,params):
        sp.transfer(
            sp.record(from_ = sp.self_address, txs= sp.list([
                sp.record(to_ = params.to_address,
                        token_id = self.data.token_id,
                        amount = params.amount
                        )
                ])
            ),
            sp.mutez(0),
            sp.contract(sp.TRecord(from_ = sp.TAddress,
                                   txs = sp.TList(
                                           sp.TRecord(to_ = sp.TAddress,
                                                      token_id = sp.TNat,
                                                      amount = sp.TNat))
                                          ), 
                                          self.data.token_address,
                                          entry_point = "transfer"
                                          ).open_some()
        )            
    
if "templates" not in __name__:
    @sp.add_test(name = "CrowdSale")
    def test():
        
        scenario = sp.test_scenario()
        
        admin = sp.test_account("Administrator")
        alice = sp.test_account("Alice")
        bob   = sp.test_account("Robert")
        vance   = sp.test_account("vance")
        
        frank = sp.test_account("frank")
        daniel = sp.test_account("daniel")
        joe = sp.test_account("joe")
        
        scenario.h1("Accounts")
        scenario.show([admin, alice, bob,vance])
        
        c1 = crowdsale(
            admin.address,
            token_address = sp.address("KT1...."),
            token_id = 0,
            rate = 1,
            cap = 42000,
            max_raise = 84000,
            startTime = sp.timestamp_from_utc(2021, 5, 17, 12, 44, 00),
            endTime = sp.timestamp_from_utc(2021, 5, 20, 12, 44, 00)
            )
        
        scenario.h1("Crowdsale")
        scenario += c1
        
        scenario.h2("Admin adds to whitelist")
        scenario += c1.addToWhitelist(alice.address).run(sender = admin)
        scenario.h2("Non admin tries to add whitelist")
        scenario += c1.addToWhitelist(bob.address).run(sender = alice, valid = False)        
        scenario.h2("Admin adds already whitelisted address")
        scenario += c1.addToWhitelist(alice.address).run(sender = admin)
        scenario += c1.addToWhitelist(bob.address).run(sender = admin)
        scenario += c1.addToWhitelist(vance.address).run(sender = admin)
        
        scenario.h2("Non-admin adds a list of users onto whitelist")
        scenario += c1.addMultipleWhitelist(sp.list([frank.address, daniel.address, joe.address])).run(sender = alice, valid = False)
        
        scenario.h2("Admin adds a list of users onto whitelist")
        scenario += c1.addMultipleWhitelist(sp.list([frank.address, daniel.address, joe.address])).run(sender = admin)
        
        scenario.h2("Non-admin tries to pause the sale")
        scenario += c1.pauseSale().run(sender = alice, valid = False)
        
        scenario.h2("admin tries to pause the sale")
        scenario += c1.pauseSale().run(sender = admin)

        scenario.h2("Whitelisted User tries to contribute during pause")
        scenario += c1.buyTokens().run(sender = alice, amount = sp.mutez(1), valid = False)

        scenario.h2("Non-admin tries to unpause the sale")
        scenario += c1.unpauseSale().run(sender = alice, valid = False)
        
        scenario.h2("admin tries to unpause the sale")
        scenario += c1.unpauseSale().run(sender = admin)        
        
        scenario.h2("Whitelisted User tries to overcontribute")
        scenario += c1.buyTokens().run(sender = alice, amount = sp.mutez(42001), valid = False)
        
        scenario.h2("Whitelisted Address Contributes")
        scenario += c1.buyTokens().run(sender = alice, amount = sp.mutez(42000))

        scenario.h2("admin withdraws contributed amount")
        scenario += c1.withdrawFunds().run(sender = admin, valid = False, now = sp.timestamp_from_utc(2021, 5, 19, 12, 44, 00))

        scenario += c1.buyTokens().run(sender = bob, amount = sp.mutez(42000))
        scenario.h2("Whitelisted User overcontribute after initial contribution")
        scenario += c1.buyTokens().run(sender = alice, amount = sp.mutez(1), valid = False)        
        scenario.h2("Already Full but tries to contribute")
        scenario += c1.buyTokens().run(sender = vance, amount = sp.mutez(2), valid = False)
        
        scenario.h2("Non admin tries to change admin")
        scenario += c1.changeAdmin(alice.address).run(sender = alice, valid = False)
        
        scenario.h2("Non-admin tries to withdraw funds")
        scenario += c1.withdrawFunds().run(sender = alice, valid = False)
        
        scenario.h2("admin withdraws contributed amount")
        scenario += c1.withdrawFunds().run(sender = admin)
        
        scenario.h2("Admin changes admin")
        scenario += c1.changeAdmin(alice.address).run(sender = admin)
        
        sp.add_compilation_target(
            "tokenSale",
            crowdsale(
                admin.address,
                token_address = sp.address("KT1...."),
                token_id = 0,
                rate = 1,
                cap = 42000,
                max_raise = 84000,
                startTime = sp.timestamp_from_utc(2021, 5, 17, 12, 44, 00),
                endTime = sp.timestamp_from_utc(2021, 5, 20, 12, 44, 00)                
            )
        )
            
