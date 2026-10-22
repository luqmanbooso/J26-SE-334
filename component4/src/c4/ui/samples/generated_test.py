from appium.webdriver.common.appiumby import AppiumBy


def step_0(driver) -> None:
    driver.find_element(
        AppiumBy.ANDROID_UIAUTOMATOR,
        'new UiSelector().text("Network and internet")',
    ).click()
