class Cart:
    discount = 0

    def __init__(self):
        self.items = []

    def add(self, sku, qty=1):
        for _ in range(qty):
            self.items.append(sku)

    def count(self):
        return len(self.items)
